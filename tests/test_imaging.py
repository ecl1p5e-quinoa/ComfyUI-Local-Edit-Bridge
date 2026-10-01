import pathlib

import numpy as np
import pytest
from PIL import Image

from local_edit_helper.core.alignment import normalize_result
from local_edit_helper.core.color_match import match_color
from local_edit_helper.core.composite import composite
from local_edit_helper.core.crop import CropSettings, calculate_crop, make_crop
from local_edit_helper.core.mask import dilate, erode, feather_mask, normalize_mask
from local_edit_helper.core.seam import seam_mask


def mask_with(block, size, value=255):
    mask = Image.new("L", size, 0)
    mask.paste(value, block)
    return mask


def test_crop_centers_on_selection():
    mask = mask_with((60, 40, 100, 80), (160, 120))
    info = calculate_crop(mask, CropSettings(crop_factor=2.0, min_size=1))
    assert info["bbox"] == [60, 40, 100, 80]
    assert info["bounds"] == [40, 20, 120, 100]
    assert info["native_size"] == [80, 80]
    assert info["export_size"] == [80, 80]
    assert info["warnings"] == []


def test_crop_clamps_at_edges_and_warns():
    mask = mask_with((0, 0, 5, 5), (30, 30))
    info = calculate_crop(mask, CropSettings(crop_factor=4.0, min_size=64))
    assert info["bounds"] == [0, 0, 30, 30]
    assert info["native_size"] == [30, 30]
    assert info["warnings"]
    assert any("clamped" in warning for warning in info["warnings"])


def test_crop_corner_still_contains_selection():
    mask = mask_with((140, 100, 155, 115), (160, 120))
    info = calculate_crop(mask, CropSettings(crop_factor=2.0, min_size=64))
    left, top, right, bottom = info["bounds"]
    assert right <= 160 and bottom <= 120
    assert left <= 140 and top <= 100 and right >= 155 and bottom >= 115


def test_crop_multiple_and_square():
    mask = mask_with((5, 5, 15, 25), (200, 200))
    info = calculate_crop(mask, CropSettings(crop_factor=1.0, min_size=1, multiple_of=16, square=True))
    assert info["native_size"] == [32, 32]


def test_crop_full_mask_and_limit_1024():
    mask = mask_with((0, 0, 3000, 1000), (3000, 1000))
    info = calculate_crop(mask, CropSettings(crop_factor=1.0, min_size=1, output_policy="limit_1024"))
    assert info["native_size"] == [3000, 1000]
    assert info["export_size"] == [1024, 341]
    assert info["warnings"]


def test_empty_mask_rejected():
    empty = Image.new("L", (40, 40), 0)
    with pytest.raises(ValueError):
        calculate_crop(empty, CropSettings())
    with pytest.raises(ValueError):
        make_crop(Image.new("RGB", (40, 40)), empty, CropSettings())


def test_make_crop_modes_and_content():
    source = Image.new("RGB", (160, 120), (10, 20, 30))
    mask = mask_with((60, 40, 100, 80), (160, 120))
    crop, crop_mask, info = make_crop(source, mask, CropSettings(crop_factor=2.0, min_size=1))
    assert crop.mode == "RGB" and crop.size == (80, 80)
    assert crop_mask.mode == "L" and crop_mask.size == (80, 80)
    assert info["bounds"] == [40, 20, 120, 100]


def test_normalize_mask_rejects_resize_and_converts():
    with pytest.raises(ValueError, match="dimensions"):
        normalize_mask(Image.new("RGB", (10, 10), "white"), (20, 20))
    result = normalize_mask(Image.new("RGB", (20, 20), "white"), (20, 20))
    assert result.mode == "L" and result.size == (20, 20)
    assert result.getextrema() == (255, 255)


def test_feather_is_inward():
    mask = mask_with((8, 8, 32, 32), (40, 40))
    feathered = feather_mask(mask, 3)
    values = np.array(feathered)
    source = np.array(mask)
    assert np.all(values <= source)
    assert values[0, 0] == 0
    assert values[20, 20] == 255
    assert 0 < values[20, 8] < 255


def test_dilate_and_erode_shapes():
    mask = mask_with((5, 5, 15, 15), (20, 20))
    grown = np.array(dilate(mask, 2))
    shrunk = np.array(erode(mask, 2))
    assert grown[3, 10] == 255 and grown[10, 10] == 255
    assert shrunk[5, 10] == 0 and shrunk[10, 10] == 255
    full = Image.new("L", (20, 20), 255)
    border = np.array(erode(full, 3))
    assert border[0, 10] == 0 and border[10, 10] == 255


def test_seam_empty_full_and_block():
    assert np.array(seam_mask(Image.new("L", (20, 20), 0), 3)).max() == 0
    full = Image.new("L", (20, 20), 255)
    band = np.array(seam_mask(full, 3))
    assert set(np.unique(band)).issubset({0, 255})
    assert band[0, 0] == 255 and band[10, 10] == 0
    block = np.array(seam_mask(mask_with((5, 5, 15, 15), (20, 20)), 2))
    assert block[4, 10] == 255 and block[10, 10] == 0 and block[0, 0] == 0


def test_strict_aspect_reject_and_resize():
    with pytest.raises(ValueError):
        normalize_result(Image.new("RGB", (100, 20)), (80, 80), "strict")
    result, warnings = normalize_result(Image.new("RGB", (40, 20)), (80, 40), "strict")
    assert result.mode == "RGBA" and result.size == (80, 40)
    assert warnings
    exact, none = normalize_result(Image.new("RGB", (80, 80)), (80, 80), "strict")
    assert exact.size == (80, 80) and none == []


def test_contain_pads_transparent():
    result, warnings = normalize_result(Image.new("RGBA", (100, 20), (255, 0, 0, 255)), (80, 80), "contain")
    pixels = np.array(result)
    assert result.mode == "RGBA" and result.size == (80, 80)
    assert pixels[0, 0, 3] == 0
    assert pixels[40, 40, 3] == 255 and tuple(pixels[40, 40, :3]) == (255, 0, 0)
    assert warnings


def ring_scene(alpha=255):
    source = Image.new("RGB", (64, 64), (128, 128, 128))
    patch = Image.new("RGBA", (64, 64), (64, 64, 64, alpha))
    mask = mask_with((22, 22, 42, 42), (64, 64))
    return source, patch, mask


def test_color_match_noop_when_disabled_or_zero():
    source, patch, mask = ring_scene()
    reference = np.array(patch)
    for kwargs in ({"enabled": False, "strength": 0.5}, {"enabled": True, "strength": 0}):
        result, report = match_color(source, patch, mask, **kwargs)
        assert np.array_equal(np.array(result), reference)
        assert report["applied"] is False


def test_color_match_skips_thin_ring():
    source, _, mask = ring_scene(alpha=0)
    _, report = match_color(source, Image.new("RGBA", (64, 64), (64, 64, 64, 0)), mask)
    assert report["applied"] is False and report["samples"] < 64


def test_color_match_flat_channel_uses_mean_only():
    source, patch, mask = ring_scene()
    result, report = match_color(source, patch, mask, strength=1.0)
    assert report["applied"] is True and report["samples"] >= 64
    assert report["scale"] == [1.0, 1.0, 1.0]
    assert abs(report["offset"][0] - 32 / 255) < 1e-4
    assert np.array(result)[10, 32, 0] == 96
    assert np.array(result)[0, 0, 0] == 96
    assert np.array_equal(np.array(result)[..., 3], np.array(patch)[..., 3])


def test_composite_outside_mask_exact_and_inside_changes():
    source = Image.fromarray(np.random.default_rng(0).integers(0, 256, (60, 80, 3), dtype=np.uint8))
    bounds = [10, 10, 50, 50]
    patch = Image.new("RGBA", (40, 40), (0, 0, 255, 255))
    mask = mask_with((20, 20, 40, 40), (80, 60))
    output, effective = composite(source, patch, mask, bounds, feather=0)
    before, after, coverage = np.array(source), np.array(output), np.array(effective)
    preserve = np.array(mask) == 0
    assert output.mode == "RGB" and output.size == source.size
    assert np.array_equal(after[preserve], before[preserve])
    assert not np.array_equal(after, before)
    assert coverage[0, 0] == 0 and coverage[30, 30] == 255
    assert tuple(after[30, 30]) == (0, 0, 255)


def test_composite_feather_stays_inward():
    source = Image.fromarray(np.random.default_rng(1).integers(0, 256, (60, 80, 3), dtype=np.uint8))
    patch = Image.new("RGBA", (40, 40), (0, 0, 255, 255))
    mask = mask_with((20, 20, 40, 40), (80, 60))
    output, effective = composite(source, patch, mask, [10, 10, 50, 50], feather=4)
    before, after, coverage = np.array(source), np.array(output), np.array(effective)
    preserve = np.array(mask) == 0
    assert np.array_equal(after[preserve], before[preserve])
    assert coverage[0, 0] == 0 and 200 <= coverage[30, 30] <= 255


def test_composite_preserves_source_alpha():
    source = Image.new("RGBA", (80, 60), (200, 100, 50, 170))
    patch = Image.new("RGBA", (40, 40), (0, 0, 255, 255))
    mask = mask_with((20, 20, 40, 40), (80, 60))
    output, _ = composite(source, patch, mask, [10, 10, 50, 50], feather=0)
    assert output.mode == "RGBA"
    assert np.all(np.array(output)[..., 3] == 170)


def test_core_stays_free_of_comfy_and_torch():
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "local_edit_helper"
    paths = list((root / "core").glob("*.py")) + [root / "prompt" / "builder.py"]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "import torch" not in text and "import comfy" not in text, path
