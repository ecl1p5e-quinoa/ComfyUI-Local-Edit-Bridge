"""The manual editor boundary. No provider, HTTP client, or ComfyUI dependencies."""
import io
import math
import uuid
from dataclasses import asdict

from PIL import Image, ImageOps, UnidentifiedImageError

from ..core.alignment import normalize_result
from ..core.color_match import match_color
from ..core.composite import composite
from ..core.crop import CropSettings, make_crop
from ..core.mask import dilate, normalize_mask
from ..core.metadata import read_metadata, save_png
from ..core.seam import seam_mask

MAX_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000


def decode_image(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose an image smaller than 32 MiB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Choose an image with at most 24 million pixels.")
            if image.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
                raise ValueError("Use an 8-bit RGB, RGBA or grayscale image.")
            image.load()
            metadata = read_metadata(image)
            oriented = ImageOps.exif_transpose(image)
            mode = "RGBA" if "A" in oriented.getbands() or "transparency" in image.info else "RGB"
            result = oriented.convert(mode)
            metadata["normalized"]["dimensions"] = list(result.size)
            return result, metadata
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The file could not be decoded as an image.") from exc


def number(value, lower, upper, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be a finite number.")
    if not lower <= value <= upper or (integer and int(value) != value):
        raise ValueError(f"{name} must be between {lower} and {upper}.")
    return int(value) if integer else float(value)


class ManualBridge:
    def __init__(self, store):
        self.store = store

    def image(self, job, key):
        with Image.open(self.store.path(job["id"], job["files"][key])) as image:
            image.load()
            return image.copy()

    def save(self, job, key, image, name=None, metadata=None):
        name = name or key + "_" + uuid.uuid4().hex + ".png"
        path = self.store.path(job["id"], name)
        temporary = path.with_name("writing_" + uuid.uuid4().hex + ".png")
        save_png(image, temporary, metadata or {"raw": {}, "normalized": {}})
        temporary.replace(path)
        job["files"][key] = name

    def create(self, data):
        image, metadata = decode_image(data)
        with self.store.lock:
            job = self.store.create(image.size, metadata)
            self.save(job, "original", image, "original.png", metadata)
            self.save(job, "mask", Image.new("L", image.size), "mask.png")
            return self.store.write(job)

    def preview(self, job_id, revision, mask_data, settings):
        mask_image, _ = decode_image(mask_data)
        if not isinstance(settings, dict):
            raise ValueError("Crop settings must be an object.")
        allowed = {"crop_factor", "min_size", "multiple_of", "square", "output_policy"}
        if set(settings) - allowed:
            raise ValueError("Unknown crop setting.")
        number(settings.get("crop_factor", 2), 1, 10, "Crop factor")
        number(settings.get("min_size", 64), 1, 16384, "Minimum size", True)
        number(settings.get("multiple_of", 1), 1, 256, "Multiple", True)
        if type(settings.get("square", False)) is not bool:
            raise ValueError("Square must be true or false.")
        crop_settings = CropSettings(**settings)
        with self.store.lock:
            job = self.store.check(job_id, revision, {"DRAFT"})
            source = self.image(job, "original")
            mask = normalize_mask(mask_image, source.size)
            self.save(job, "mask", mask, "draft_mask.png")
            job["crop_settings"] = asdict(crop_settings)
            job["warnings"] = []
            if mask.getbbox() is None:
                job["crop"] = None
                for key in ("crop", "crop_mask", "preview"):
                    job["files"].pop(key, None)
                job["warnings"] = ["Paint an edit mask to preview a crop."]
            else:
                crop, crop_mask, info = make_crop(source, mask, crop_settings)
                job["crop"] = info
                job["warnings"] = info["warnings"]
                self.save(job, "crop", crop, "draft_crop.png")
                self.save(job, "crop_mask", crop_mask, "draft_crop_mask.png")
            return self.store.write(job)

    def prepare(self, job_id, revision, prompt):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
            raise ValueError("Provide a prompt between 1 and 16000 characters.")
        with self.store.lock:
            job = self.store.check(job_id, revision, {"DRAFT"})
            source, mask = self.image(job, "original"), self.image(job, "mask")
            crop, crop_mask, info = make_crop(source, mask, CropSettings(**job["crop_settings"]))
            self.save(job, "mask", mask, "mask.png")
            self.save(job, "crop", crop, "crop.png")
            self.save(job, "crop_mask", crop_mask, "crop_mask.png")
            preview = crop.convert("RGBA")
            overlay = Image.new("RGBA", crop.size, (255, 80, 70, 0))
            overlay.putalpha(crop_mask.point(lambda value: value // 3))
            preview = Image.alpha_composite(preview, overlay)
            self.save(job, "preview", preview, "overlay.png")
            job["handoff"] = "crop_overlay"
            self.store.path(job_id, "prompt.txt").write_text(prompt, encoding="utf-8")
            job["files"]["prompt"] = "prompt.txt"
            job.update(crop=info, prompt=prompt, state="READY_FOR_EXTERNAL_EDIT", warnings=info["warnings"])
            return self.store.write(job)

    def rework(self, job_id, revision, step, prompt, prompt_inputs=None):
        if step not in {"mask", "crop", "prompt", "import", "blend", "final"}:
            raise ValueError("Unknown editing step.")
        if not isinstance(prompt, str) or len(prompt) > 16000:
            raise ValueError("Prompt must be at most 16000 characters.")
        with self.store.lock:
            job = self.store.check(job_id, revision, {"DRAFT", "READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT", "RESULT_IMPORTED", "COMPOSITED", "FINALIZED"})
            if step == "import" and job["state"] == "DRAFT":
                raise ValueError("Prepare the handoff first.")
            if step == "blend" and "aligned" not in job["files"]:
                raise ValueError("Import a result first.")
            if step == "final" and "composite" not in job["files"]:
                raise ValueError("Composite the result first.")
            if prompt_inputs is not None:
                if (not isinstance(prompt_inputs, dict) or set(prompt_inputs) != {"request", "context"}
                        or any(not isinstance(value, str) or len(value) > 16000 for value in prompt_inputs.values())):
                    raise ValueError("Invalid prompt inputs.")
                job["prompt_inputs"] = prompt_inputs
            job["prompt"] = prompt
            backup = self.store.checkpoint(job)
            keep = {"original", "mask", "crop", "crop_mask", "preview", "prompt"}
            if step in {"mask", "crop", "prompt"}:
                job["state"] = "DRAFT"
                keep -= {"preview", "prompt"}
            elif step == "import":
                job["state"] = "RESULT_IMPORTED" if "aligned" in job["files"] else "READY_FOR_EXTERNAL_EDIT"
                keep |= {"returned", "aligned"}
            elif step == "blend":
                job["state"] = "RESULT_IMPORTED"
                keep |= {"returned", "aligned"}
            else:
                job["state"] = "COMPOSITED"
                keep |= {"returned", "aligned", "composite", "seam", "matched", "composite_mask"}
            job["files"] = {key: name for key, name in job["files"].items() if key in keep}
            # Settings remain editable; only derived processing results are invalidated.
            if step != "final":
                job["processing"].pop("color_report", None)
            if step in {"mask", "crop", "prompt"}:
                if "import" in job:
                    job["import"] = {"policy": job["import"]["policy"]}
            job.update(warnings=[], rework_backup=backup, rework_step=step, rework_undone=False)
            return self.store.write(job)

    def undo_rework(self, job_id, revision, prompt, prompt_inputs=None):
        with self.store.lock:
            job = self.store.check(job_id, revision, {"DRAFT", "READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT", "RESULT_IMPORTED", "COMPOSITED", "FINALIZED"})
            if not job.get("rework_backup"):
                raise ValueError("No step rework to undo.")
            if not isinstance(prompt, str) or len(prompt) > 16000:
                raise ValueError("Prompt must be at most 16000 characters.")
            if prompt_inputs is not None:
                if (not isinstance(prompt_inputs, dict) or set(prompt_inputs) != {"request", "context"}
                        or any(not isinstance(value, str) or len(value) > 16000 for value in prompt_inputs.values())):
                    raise ValueError("Invalid prompt inputs.")
                job["prompt_inputs"] = prompt_inputs
            job["prompt"] = prompt
            restored, backup = self.store.restore_checkpoint(job)
            restored.update(revision=revision, rework_backup=backup, rework_step=job["rework_step"],
                            rework_undone=not job.get("rework_undone", False))
            return self.store.write(restored)

    def sent(self, job_id, revision):
        with self.store.lock:
            job = self.store.check(job_id, revision, {"READY_FOR_EXTERNAL_EDIT"})
            job["state"] = "WAITING_FOR_RESULT"
            return self.store.write(job)

    def import_result(self, job_id, revision, data, policy):
        result, _ = decode_image(data)
        with self.store.lock:
            job = self.store.check(job_id, revision,
                                   {"READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT", "RESULT_IMPORTED", "COMPOSITED"})
            if job.get("handoff") == "original_overlay":
                normalized, warnings = normalize_result(result, job["source_size"], policy)
                normalized = normalized.crop(job["crop"]["bounds"])
            else:
                # Jobs already handed off as crops still expect a crop on return.
                normalized, warnings = normalize_result(result, job["crop"]["export_size"], policy)
                native_size = tuple(job["crop"]["native_size"])
                if normalized.size != native_size:
                    normalized = normalized.resize(native_size, Image.Resampling.LANCZOS)
                    warnings.append("The exported crop was restored to its native pixel dimensions.")
            self.save(job, "returned", result)
            self.save(job, "aligned", normalized)
            for key in ("composite", "seam", "matched", "composite_mask", "final"):
                job["files"].pop(key, None)
            job["import"] = {"policy": policy, "input_size": list(result.size), "alignment": "none"}
            job["processing"] = {}
            job.update(state="RESULT_IMPORTED", warnings=warnings)
            return self.store.write(job)

    def process(self, job_id, revision, color_enabled=True, strength=1.0, feather=8, seam_width=8, debug=False, mask_expansion=0):
        if type(color_enabled) is not bool or type(debug) is not bool:
            raise ValueError("Color enabled and debug must be true or false.")
        strength = number(strength, 0, 1, "Color strength")
        feather = number(feather, 0, 128, "Feather", True)
        seam_width = number(seam_width, 0, 128, "Seam width", True)
        mask_expansion = number(mask_expansion, 0, 128, "Mask expansion", True)
        with self.store.lock:
            job = self.store.check(job_id, revision, {"RESULT_IMPORTED", "COMPOSITED"})
            source, mask = self.image(job, "original"), self.image(job, "mask")
            patch, bounds = self.image(job, "aligned"), job["crop"]["bounds"]
            expanded = dilate(mask, mask_expansion)
            box = expanded.getbbox()
            expansion_clipped = bool(box and (box[0] < bounds[0] or box[1] < bounds[1]
                                             or box[2] > bounds[2] or box[3] > bounds[3]))
            mask = Image.new("L", source.size)
            mask.paste(expanded.crop(bounds), bounds)
            matched, report = match_color(source.crop(bounds).convert("RGB"), patch, mask.crop(bounds),
                                          enabled=color_enabled, strength=strength)
            output, effective = composite(source, matched, mask, bounds, feather=feather)
            seam = seam_mask(mask, seam_width)
            self.save(job, "composite", output, metadata=job["source_metadata"])
            self.save(job, "seam", seam)
            if debug:
                self.save(job, "matched", matched)
                self.save(job, "composite_mask", effective)
            else:
                for key in ("matched", "composite_mask"):
                    job["files"].pop(key, None)
            job["processing"] = {"color_enabled": color_enabled, "strength": strength, "feather": feather,
                                 "seam_width": seam_width, "color_report": report, "debug": debug,
                                 "mask_expansion": mask_expansion, "expansion_clipped": expansion_clipped}
            job["state"] = "COMPOSITED"
            return self.store.write(job)

    def finalize(self, job_id, revision):
        with self.store.lock:
            job = self.store.check(job_id, revision, {"COMPOSITED"})
            image = self.image(job, "composite")
            path = self.store.path(job_id, "final.png")
            temporary = path.with_name("final_" + uuid.uuid4().hex + ".png")
            save_png(image, temporary, job["source_metadata"],
                     provenance={"job_id": job_id, "crop": job["crop"], "processing": job["processing"]})
            temporary.replace(path)
            job["files"]["final"] = "final.png"
            job["state"] = "FINALIZED"
            return self.store.write(job)
