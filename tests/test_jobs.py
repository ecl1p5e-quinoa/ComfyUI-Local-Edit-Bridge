import io
import json

import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from local_edit_helper.bridge.manual import ManualBridge, decode_image
from local_edit_helper.core.jobs import ConflictError, JobStore
from local_edit_helper.prompt.builder import build_prompt
from local_edit_helper.core.mask import dilate
from local_edit_helper.core.seam import seam_mask


def png(image, metadata=None):
    buffer = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    for key, value in (metadata or {}).items():
        info.add_text(key, value)
    image.save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


@pytest.fixture
def scene():
    y, x = np.mgrid[:120, :160]
    image = Image.fromarray(np.stack((x, y, (x + y) // 2), axis=-1).astype(np.uint8))
    mask = np.zeros((120, 160), dtype=np.uint8)
    mask[40:80, 60:100] = 255
    return image, Image.fromarray(mask)


def prepared(tmp_path, scene):
    image, mask = scene
    bridge = ManualBridge(JobStore(tmp_path))
    job = bridge.create(png(image, {"parameters": "a landscape\nSteps: 20, Sampler: Euler, CFG scale: 7, Seed: 42"}))
    job = bridge.preview(job["id"], job["revision"], png(mask), {"crop_factor": 2, "min_size": 1})
    job = bridge.prepare(job["id"], job["revision"], build_prompt("Make the object blue."))
    return bridge, job


def test_complete_round_trip_and_restart(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    for name in ("original.png", "mask.png", "crop.png", "crop_mask.png", "prompt.txt", "metadata.json", "overlay.png"):
        assert bridge.store.path(job["id"], name).is_file()
    crop = bridge.image(job, "crop").convert("RGBA")
    edited = np.array(crop)
    edited[25:55, 25:55, :3] = [20, 30, 240]
    job = bridge.sent(job["id"], job["revision"])
    job = bridge.import_result(job["id"], job["revision"], png(Image.fromarray(edited)), "strict")
    job = bridge.process(job["id"], job["revision"], color_enabled=True, strength=0.5, feather=4, seam_width=3, debug=True)
    before, mask = scene
    after = np.array(bridge.image(job, "composite"))
    preserve = np.array(mask) == 0
    assert np.array_equal(after[preserve], np.array(before)[preserve])
    assert not np.array_equal(after, np.array(before))
    assert after.shape == np.array(before).shape
    job = bridge.finalize(job["id"], job["revision"])
    restarted = ManualBridge(JobStore(tmp_path))
    assert restarted.store.read(job["id"]) == job
    final = restarted.image(job, "final")
    assert final.size == before.size
    assert "parameters" in final.info
    assert np.array_equal(np.array(final)[preserve], np.array(before)[preserve])
    assert restarted.store.listing()["jobs"][0]["state"] == "FINALIZED"


def test_empty_mask_persists_but_cannot_prepare(tmp_path, scene):
    bridge = ManualBridge(JobStore(tmp_path))
    job = bridge.create(png(scene[0]))
    job = bridge.preview(job["id"], job["revision"], png(Image.new("L", scene[0].size)), {})
    assert job["crop"] is None
    with pytest.raises(ValueError):
        bridge.prepare(job["id"], job["revision"], "Edit")


def test_revision_and_frozen_contract(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    with pytest.raises(ConflictError):
        bridge.sent(job["id"], job["revision"] - 1)
    with pytest.raises(ConflictError):
        bridge.preview(job["id"], job["revision"], png(scene[1]), {})
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "strict")
    job = bridge.process(job["id"], job["revision"])
    old_name = job["files"]["composite"]
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "strict")
    assert "composite" not in job["files"]
    assert not bridge.store.path(job["id"], old_name).exists()
    with pytest.raises(ConflictError):
        bridge.finalize(job["id"], job["revision"])


def test_corrupt_manifest_and_paths(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    with pytest.raises(ValueError):
        bridge.store.read("../elsewhere")
    with pytest.raises(ValueError):
        bridge.store.path(job["id"], "../original.png")
    with pytest.raises(FileNotFoundError):
        bridge.store.artifact(job["id"], "secret.txt")
    path = bridge.store.path(job["id"], "metadata.json")
    path.write_text("not json")
    with pytest.raises(ValueError, match="Malformed"):
        bridge.store.read(job["id"])
    listing = bridge.store.listing()
    assert len(listing["errors"]) == 1
    assert not listing["jobs"]


@pytest.mark.parametrize("change", [
    {"schema_version": 42}, {"schema_version": True}, {"revision": -1}, {"state": "BOGUS"},
    {"state": []}, {"updated_at": None}, {"source_metadata": {}},
    {"files": {"original": "../elsewhere.png"}}, {"source_size": [0, 1]},
    {"crop": {"bounds": [-1, 0, 20, 20]}},
])
def test_manifest_validation(tmp_path, scene, change):
    bridge, job = prepared(tmp_path, scene)
    job.update(change)
    bridge.store.path(job["id"], "metadata.json").write_text(json.dumps(job), encoding="utf-8")
    with pytest.raises(ValueError):
        bridge.store.read(job["id"])


def test_import_validation_and_alpha(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    with pytest.raises(ValueError):
        bridge.import_result(job["id"], job["revision"], b"invalid", "strict")
    with pytest.raises(ValueError):
        bridge.import_result(job["id"], job["revision"], png(Image.new("RGB", (100, 20))), "strict")
    transparent = Image.new("RGBA", (100, 20), (240, 0, 0, 0))
    job = bridge.import_result(job["id"], job["revision"], png(transparent), "contain")
    job = bridge.process(job["id"], job["revision"], feather=0)
    assert np.array_equal(np.array(bridge.image(job, "composite")), np.array(scene[0]))
    job = bridge.finalize(job["id"], job["revision"])
    with pytest.raises(ConflictError):
        bridge.import_result(job["id"], job["revision"], png(transparent), "contain")


def test_source_alpha_and_metadata(tmp_path, scene):
    rgba = scene[0].convert("RGBA")
    rgba.putalpha(Image.new("L", rgba.size, 170))
    bridge, job = prepared(tmp_path, (rgba, scene[1]))
    job = bridge.import_result(job["id"], job["revision"], png(Image.new("RGB", tuple(job["crop"]["native_size"]), "blue")), "strict")
    job = bridge.process(job["id"], job["revision"])
    result = bridge.image(job, "composite")
    assert result.mode == "RGBA"
    assert np.all(np.array(result)[..., 3] == 170)


def test_invalid_values(tmp_path, scene):
    bridge = ManualBridge(JobStore(tmp_path))
    job = bridge.create(png(scene[0]))
    for settings in ({"crop_factor": float("nan")}, {"square": "false"}, {"unknown": 1}, {"min_size": -1}):
        with pytest.raises(ValueError):
            bridge.preview(job["id"], job["revision"], png(scene[1]), settings)
    with pytest.raises(ValueError):
        decode_image(png(Image.new("I;16", (10, 10))))


def test_import_validates_export_ratio_before_restoring_native_size(tmp_path):
    bridge = ManualBridge(JobStore(tmp_path))
    source = Image.new("RGB", (1, 2000), "gray")
    job = bridge.create(png(source))
    job = bridge.preview(job["id"], job["revision"], png(Image.new("L", source.size, 255)),
                         {"crop_factor": 1, "min_size": 1, "output_policy": "limit_1024"})
    job = bridge.prepare(job["id"], job["revision"], "Change the color.")
    assert job["crop"]["export_size"] == [1, 1024]
    # Persist an already-exported crop job to verify its original import contract.
    job.pop("handoff")
    bridge.store.write(job)
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "strict")
    assert bridge.image(job, "aligned").size == source.size

@pytest.mark.parametrize('step,state', [('mask','DRAFT'), ('crop','DRAFT'), ('prompt','DRAFT'), ('import','RESULT_IMPORTED'), ('blend','RESULT_IMPORTED'), ('final','COMPOSITED')])
def test_rework_restore_and_redo_in_session(tmp_path, scene, step, state):
    bridge, job = prepared(tmp_path, scene)
    job = bridge.import_result(job['id'], job['revision'], png(bridge.image(job, 'crop')), 'strict')
    job = bridge.process(job['id'], job['revision'])
    job = bridge.finalize(job['id'], job['revision'])
    final_bytes = bridge.store.path(job['id'], job['files']['final']).read_bytes()
    mask_bytes = np.array(bridge.image(job, 'mask'))
    prompt = job['prompt']
    original_revision = job['revision']
    job = bridge.rework(job['id'], job['revision'], step, prompt)
    assert job['state'] == state
    assert 'final' not in job['files']
    assert job['prompt'] == prompt
    assert np.array_equal(np.array(bridge.image(job, 'mask')), mask_bytes)
    if step in {'mask', 'crop', 'prompt'}:
        assert 'aligned' not in job['files']
    if step != 'final':
        assert 'composite' not in job['files']
    with pytest.raises(ConflictError):
        bridge.undo_rework(job['id'], original_revision, job['prompt'])
    bridge = ManualBridge(bridge.store)
    job = bridge.undo_rework(job['id'], job['revision'], job['prompt'])
    assert job['state'] == 'FINALIZED'
    assert job['prompt'] == prompt
    assert bridge.store.path(job['id'], job['files']['final']).read_bytes() == final_bytes
    assert np.array_equal(np.array(bridge.image(job, 'mask')), mask_bytes)
    job = bridge.undo_rework(job['id'], job['revision'], job['prompt'])
    assert job['state'] == state
    assert not job['rework_undone']


def test_snapshot_survives_overwritten_export(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    old_crop = np.array(bridge.image(job, 'crop'))
    job = bridge.rework(job['id'], job['revision'], 'mask', 'keep me')
    job = bridge.preview(job['id'], job['revision'], png(Image.new('L', scene[0].size, 255)), {})
    job = bridge.prepare(job['id'], job['revision'], 'keep me')
    job = bridge.undo_rework(job['id'], job['revision'], 'keep me')
    assert np.array_equal(np.array(bridge.image(job, 'crop')), old_crop)
    assert job['prompt'] == 'keep me'


def test_crop_overlay_handoff_and_color_defaults(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    original = np.array(bridge.image(job, "crop").convert("RGB"))
    guide = np.array(bridge.image(job, "preview").convert("RGB"))
    selected = np.array(bridge.image(job, "crop_mask")) > 0
    assert job["handoff"] == "crop_overlay"
    assert original.shape == guide.shape
    assert np.array_equal(original[~selected], guide[~selected])
    assert np.any(original[selected] != guide[selected])
    assert np.all(guide[selected, 0] > original[selected, 0])
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "strict")
    assert np.array_equal(np.array(bridge.image(job, "aligned").convert("RGB")), np.array(scene[0].crop(job["crop"]["bounds"])))
    job = bridge.process(job["id"], job["revision"])
    assert job["processing"]["color_enabled"] is True
    assert job["processing"]["strength"] == 1


def test_full_return_scaled_and_mask_preserved(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    result = scene[0].copy()
    result.paste((0, 0, 255), (60, 40, 100, 80))
    result = result.crop(job["crop"]["bounds"])
    result = result.resize((result.width * 2, result.height * 2), Image.Resampling.NEAREST)
    job = bridge.import_result(job["id"], job["revision"], png(result), "strict")
    job = bridge.process(job["id"], job["revision"], color_enabled=False, feather=0)
    output = np.array(bridge.image(job, "composite"))
    outside = np.array(scene[1]) == 0
    assert np.array_equal(output[outside], np.array(scene[0])[outside])
    assert tuple(output[60, 80]) == (0, 0, 255)


def test_overlay_uses_same_downscaled_crop(tmp_path):
    bridge = ManualBridge(JobStore(tmp_path))
    source = Image.new("RGB", (2400, 1600), "gray")
    mask = Image.new("L", source.size)
    mask.paste(255, (600, 400, 1800, 1200))
    job = bridge.create(png(source))
    job = bridge.preview(job["id"], job["revision"], png(mask), {"crop_factor": 1.5, "output_policy": "limit_1024"})
    job = bridge.prepare(job["id"], job["revision"], "Edit image 1 using image 2 as a guide.")
    assert bridge.image(job, "crop").size == bridge.image(job, "preview").size == tuple(job["crop"]["export_size"])
    assert max(bridge.image(job, "preview").size) == 1024
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "strict")
    assert bridge.image(job, "aligned").size == tuple(job["crop"]["native_size"])


def test_latest_artifacts_only_and_ephemeral_undo(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    directory = bridge.store.directory(job["id"])
    unrelated = directory / "my-notes.txt"
    unrelated.write_text("keep this")
    for _ in range(3):
        job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "contain")
        job = bridge.process(job["id"], job["revision"], debug=True)
        job = bridge.finalize(job["id"], job["revision"])
        assert {p.name for p in directory.iterdir()} == set(job["files"].values()) | {"metadata.json", "my-notes.txt"}
        job = bridge.rework(job["id"], job["revision"], "import", job["prompt"])
    assert not list(directory.glob("history_*"))
    assert bridge.store.undo_snapshot["directory"].name not in str(directory)
    job = bridge.undo_rework(job["id"], job["revision"], job["prompt"])
    assert job["state"] == "FINALIZED"
    assert {p.name for p in directory.iterdir()} == set(job["files"].values()) | {"metadata.json", "my-notes.txt"}
    restarted = ManualBridge(JobStore(tmp_path))
    current = restarted.store.read(job["id"])
    assert "rework_backup" not in current
    assert current["state"] == "FINALIZED"
    with pytest.raises(ValueError, match="No step rework"):
        restarted.undo_rework(job["id"], job["revision"], job["prompt"])
    assert unrelated.read_text() == "keep this"


def test_rework_preserves_authored_inputs_and_folder(tmp_path, scene):
    bridge, job = prepared(tmp_path, scene)
    directory = bridge.store.export_handoff(job["id"], job["revision"])
    assert {p.name for p in directory.iterdir()} == {"01-crop.png", "02-overlay.png", "prompt.txt"}
    settings = job["crop_settings"].copy()
    original_mask = np.array(bridge.image(job, "mask"))
    for step in ("mask", "crop", "prompt"):
        job = bridge.rework(job["id"], job["revision"], step, "My carefully written prompt", {"request": "My request", "context": "My context"})
        assert job["prompt"] == "My carefully written prompt"
        assert job["prompt_inputs"] == {"request": "My request", "context": "My context"}
        assert job["crop_settings"] == settings
        assert np.array_equal(np.array(bridge.image(job, "mask")), original_mask)
        assert list(directory.iterdir()) == []
        job = bridge.prepare(job["id"], job["revision"], job["prompt"])
        assert (directory / "prompt.txt").read_text() == job["prompt"]
        assert {p.name for p in directory.iterdir()} == {"01-crop.png", "02-overlay.png", "prompt.txt"}
    job = bridge.import_result(job["id"], job["revision"], png(bridge.image(job, "crop")), "contain")
    job = bridge.process(job["id"], job["revision"], strength=.35, feather=3, seam_width=5)
    job = bridge.rework(job["id"], job["revision"], "blend", job["prompt"])
    assert job["processing"]["strength"] == .35
    assert job["processing"]["feather"] == 3
    assert job["processing"]["seam_width"] == 5
    assert "composite" not in job["files"]

@pytest.mark.parametrize('expansion', [0, 4, 128])
def test_mask_expansion_blend_and_seam(tmp_path, scene, expansion):
    bridge, job = prepared(tmp_path, scene)
    original_mask = np.array(bridge.image(job, 'mask'))
    patch = Image.new('RGB', tuple(job['crop']['export_size']), 'blue')
    job = bridge.import_result(job['id'], job['revision'], png(patch), 'strict')
    job = bridge.process(job['id'], job['revision'], color_enabled=False, feather=0, mask_expansion=expansion)
    expected = Image.new('L', scene[0].size)
    expanded = dilate(scene[1], expansion)
    expected.paste(expanded.crop(job['crop']['bounds']), job['crop']['bounds'])
    selected = np.array(expected) > 0
    output = np.array(bridge.image(job, 'composite'))
    assert np.all(output[selected] == [0, 0, 255])
    assert np.array_equal(output[~selected], np.array(scene[0])[~selected])
    assert np.array_equal(np.array(bridge.image(job, 'mask')), original_mask)
    assert np.array_equal(np.array(bridge.image(job, 'seam')), np.array(seam_mask(expected, 8)))
    assert job['processing']['mask_expansion'] == expansion
    assert job['processing']['expansion_clipped'] == (expansion == 128)
    job = bridge.process(job['id'], job['revision'], color_enabled=False, feather=0, mask_expansion=0)
    assert np.array_equal(np.array(bridge.image(job, 'composite'))[original_mask == 0], np.array(scene[0])[original_mask == 0])


@pytest.mark.parametrize('expansion', [-1, 129, .5, True, float('nan')])
def test_invalid_mask_expansion(tmp_path, scene, expansion):
    bridge, job = prepared(tmp_path, scene)
    job = bridge.import_result(job['id'], job['revision'], png(bridge.image(job, 'crop')), 'strict')
    with pytest.raises(ValueError, match='Mask expansion'):
        bridge.process(job['id'], job['revision'], mask_expansion=expansion)
