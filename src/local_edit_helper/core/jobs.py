"""Versioned disk manifests; callers hold the store lock for a whole operation."""
import json
import re
import shutil
import tempfile
from copy import deepcopy
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATES = {"DRAFT", "READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT",
          "RESULT_IMPORTED", "COMPOSITED", "FINALIZED"}
ID_PATTERN = re.compile(r"[0-9a-f]{32}")
FILE_PATTERN = re.compile(r"[a-z][a-z0-9_-]*\.(?:png|json|txt)")


class ConflictError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self.undo_snapshot = None

    def directory(self, job_id):
        if not isinstance(job_id, str) or not ID_PATTERN.fullmatch(job_id):
            raise ValueError("Invalid job ID.")
        path = (self.root / job_id).resolve()
        if path.parent != self.root:
            raise ValueError("Job directory is outside the configured storage.")
        return path

    def path(self, job_id, name):
        if not isinstance(name, str) or not FILE_PATTERN.fullmatch(name):
            raise ValueError("Invalid artifact name.")
        directory = self.directory(job_id)
        path = (directory / name).resolve()
        if path.parent != directory:
            raise ValueError("Artifact is outside the job directory.")
        return path

    def read(self, job_id):
        with self.lock:
            try:
                job = json.loads(self.path(job_id, "metadata.json").read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("Malformed job manifest.") from exc
            if not isinstance(job, dict) or type(job.get("schema_version")) is not int or job["schema_version"] != 1:
                raise ValueError("Unsupported or malformed job schema.")
            if job.get("id") != job_id or not isinstance(job.get("state"), str) or job["state"] not in STATES:
                raise ValueError("Invalid job identity or state.")
            if not all(isinstance(job.get(key), str) for key in ("created_at", "updated_at")):
                raise ValueError("Invalid job timestamps.")
            if type(job.get("revision")) is not int or job["revision"] < 0:
                raise ValueError("Invalid job revision.")
            size = job.get("source_size")
            if not isinstance(size, list) or len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
                raise ValueError("Invalid source dimensions in manifest.")
            files = job.get("files")
            if not isinstance(files, dict) or "original" not in files:
                raise ValueError("Missing job artifacts.")
            for name in files.values():
                self.path(job_id, name)
            metadata = job.get("source_metadata")
            if not isinstance(metadata, dict) or not isinstance(metadata.get("raw"), dict) or not isinstance(metadata.get("normalized"), dict):
                raise ValueError("Invalid source metadata in manifest.")
            if not isinstance(job.get("crop_settings"), dict) or not isinstance(job.get("processing"), dict) or not isinstance(job.get("prompt"), str):
                raise ValueError("Invalid job settings in manifest.")
            crop = job.get("crop")
            if crop is not None:
                bounds = crop.get("bounds") if isinstance(crop, dict) else None
                if (not isinstance(bounds, list) or len(bounds) != 4
                        or any(type(x) is not int for x in bounds)
                        or not 0 <= bounds[0] < bounds[2] <= size[0]
                        or not 0 <= bounds[1] < bounds[3] <= size[1]):
                    raise ValueError("Invalid crop coordinates in manifest.")
                if crop.get("native_size") != [bounds[2] - bounds[0], bounds[3] - bounds[1]]:
                    raise ValueError("Crop dimensions do not match stored coordinates.")
                export_size = crop.get("export_size")
                if not isinstance(export_size, list) or len(export_size) != 2 or any(type(value) is not int or value < 1 for value in export_size):
                    raise ValueError("Invalid exported crop dimensions.")
            required = {"original", "mask"}
            if job["state"] != "DRAFT":
                required |= {"crop", "crop_mask", "prompt", "preview"}
                if crop is None:
                    raise ValueError("Prepared job has no crop.")
            if job["state"] in {"RESULT_IMPORTED", "COMPOSITED", "FINALIZED"}:
                required |= {"returned", "aligned"}
            if job["state"] in {"COMPOSITED", "FINALIZED"}:
                required |= {"composite", "seam"}
            if job["state"] == "FINALIZED":
                required.add("final")
            if not required <= files.keys():
                raise ValueError("Job state is missing required artifacts.")
            if not self.undo_snapshot or job.get("rework_backup") != self.undo_snapshot["token"]:
                for key in ("rework_backup", "rework_step", "rework_undone"):
                    job.pop(key, None)
            return job

    def check(self, job_id, revision, states):
        job = self.read(job_id)
        if type(revision) is not int or revision != job["revision"]:
            raise ConflictError("Job changed in another tab. Reopen it before continuing.")
        if job["state"] not in states:
            raise ConflictError("This action is unavailable in state " + job["state"] + ".")
        return job

    def write(self, job):
        job["updated_at"] = now()
        job["revision"] += 1
        path = self.path(job["id"], "metadata.json")
        temporary = path.with_name("manifest-" + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
        self.prune(job)
        if job["state"] == "DRAFT":
            self.clear_handoff(job["id"])
        elif self.handoff_directory(job["id"]).exists() and job.get("handoff") == "crop_overlay":
            self.export_handoff(job["id"], job["revision"])
        return job

    def handoff_directory(self, job_id):
        directory = self.directory(job_id)
        target = directory / "gpt-handoff"
        if target.is_symlink() or target.resolve().parent != directory:
            raise ValueError("Handoff folder is outside the job directory.")
        return target

    def clear_handoff(self, job_id):
        target = self.handoff_directory(job_id)
        if target.is_dir():
            for name in ("01-crop.png", "02-overlay.png", "prompt.txt"):
                path = target / name
                if path.is_symlink():
                    raise ValueError("Handoff files must not be symbolic links.")
                path.unlink(missing_ok=True)

    def export_handoff(self, job_id, revision):
        with self.lock:
            job = self.check(job_id, revision, STATES - {"DRAFT"})
            if job.get("handoff") != "crop_overlay":
                raise ValueError("Prepare step 3 again to export the two-image handoff.")
            target = self.handoff_directory(job_id)
            target.mkdir(exist_ok=True)
            names = {"01-crop.png", "02-overlay.png", "prompt.txt"}
            if any(path.name not in names or path.is_symlink() or not path.is_file() for path in target.iterdir()):
                raise ValueError("Move extra files out of the gpt-handoff folder before preparing it again.")
            for key, name in (("crop", "01-crop.png"), ("preview", "02-overlay.png"), ("prompt", "prompt.txt")):
                shutil.copyfile(self.path(job_id, job["files"][key]), target / name)
            return target

    def prune(self, job):
        keep = set(job["files"].values()) | {"metadata.json"}
        fixed = {"original.png", "mask.png", "crop.png", "crop_mask.png", "overlay.png", "preview.png",
                 "prompt.txt", "final.png", "draft_mask.png", "draft_crop.png", "draft_crop_mask.png"}
        generated = re.compile(r"(?:history|returned|aligned|composite|seam|matched|composite_mask|mask|crop|crop_mask|preview|writing|final)_[0-9a-f]{32}\.(?:png|json|txt)")
        for entry in self.directory(job["id"]).iterdir():
            if entry.name in keep or entry.is_symlink() or not entry.is_file():
                continue
            if entry.name in fixed or generated.fullmatch(entry.name):
                try:
                    self.path(job["id"], entry.name).unlink()
                except PermissionError:
                    # Windows may still be serving this image; retry on the next save/open.
                    continue

    def snapshot(self, job):
        saved = deepcopy(job)
        for key in ("rework_backup", "rework_step", "rework_undone"):
            saved.pop(key, None)
        directory = tempfile.TemporaryDirectory(prefix="gpt-local-edit-undo-")
        for name in set(saved["files"].values()):
            shutil.copyfile(self.path(job["id"], name), Path(directory.name) / name)
        return {"token": uuid.uuid4().hex, "job": saved, "directory": directory}

    def checkpoint(self, job):
        snapshot = self.snapshot(job)
        previous = self.undo_snapshot
        self.undo_snapshot = snapshot
        if previous:
            previous["directory"].cleanup()
        return snapshot["token"]

    def restore_checkpoint(self, job):
        previous = self.undo_snapshot
        if not previous or previous["token"] != job.get("rework_backup") or previous["job"]["id"] != job["id"]:
            raise ValueError("No step rework to undo in this server session.")
        snapshot = self.snapshot(job)
        restored = deepcopy(previous["job"])
        for name in set(restored["files"].values()):
            shutil.copyfile(Path(previous["directory"].name) / name, self.path(job["id"], name))
        self.undo_snapshot = snapshot
        previous["directory"].cleanup()
        return restored, snapshot["token"]

    def create(self, size, metadata):
        self.root.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4().hex
        self.directory(job_id).mkdir()
        return {"schema_version": 1, "id": job_id, "state": "DRAFT", "revision": 0,
                "created_at": now(), "updated_at": now(), "source_size": list(size),
                "source_metadata": metadata, "crop": None, "crop_settings": {},
                "mask_convention": "white=edit, black=preserve", "prompt": "",
                "processing_defaults": {"color_enabled": True, "strength": 1.0, "feather": 8, "seam_width": 8, "mask_expansion": 0},
                "processing": {}, "warnings": [], "files": {"original": "original.png"}}

    def listing(self):
        jobs, errors = [], []
        if not self.root.exists():
            return {"jobs": jobs, "errors": errors}
        with self.lock:
            for path in self.root.iterdir():
                if not ID_PATTERN.fullmatch(path.name) or not path.is_dir():
                    continue
                try:
                    job = self.read(path.name)
                    jobs.append({key: job[key] for key in ("id", "state", "updated_at", "source_size")})
                except (ValueError, OSError) as exc:
                    errors.append({"id": path.name, "error": str(exc)})
        jobs.sort(key=lambda job: job["updated_at"], reverse=True)
        return {"jobs": jobs, "errors": errors}

    def artifact(self, job_id, name):
        job = self.read(job_id)
        if name != "metadata.json" and name not in job["files"].values():
            raise FileNotFoundError("Artifact is not part of this job.")
        return self.path(job_id, name)
