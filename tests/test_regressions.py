import io
import json

import numpy as np
import pytest
from PIL import Image

from local_edit_helper.bridge.manual import decode_image
from local_edit_helper.core.alignment import normalize_result
from local_edit_helper.core.color_match import match_color
from local_edit_helper.core.composite import composite
from local_edit_helper.core.crop import CropSettings, calculate_crop
from local_edit_helper.core.mask import dilate
from local_edit_helper.core.metadata import read_metadata
from local_edit_helper.core.seam import seam_mask
from local_edit_helper.prompt.builder import build_prompt


@pytest.mark.parametrize('box', [(0, 0, 10, 10), (90, 0, 100, 10), (0, 70, 10, 80),
                                  (90, 70, 100, 80), (0, 30, 10, 50), (90, 30, 100, 50),
                                  (40, 0, 60, 10), (40, 70, 60, 80)])
@pytest.mark.parametrize('factor', [1, 2.5])
def test_every_crop_edge_and_corner(box, factor):
    mask = Image.new('L', (100, 80))
    mask.paste(255, box)
    crop = calculate_crop(mask, CropSettings(crop_factor=factor, min_size=1))
    left, top, right, bottom = crop['bounds']
    assert 0 <= left <= box[0] < box[2] <= right <= 100
    assert 0 <= top <= box[1] < box[3] <= bottom <= 80
    if factor == 1:
        assert crop['bounds'] == list(box)


def test_square_preserved_when_shorter_edge_can_contain_mask():
    mask = Image.new('L', (120, 80))
    mask.paste(255, (30, 30, 50, 50))
    assert calculate_crop(mask, CropSettings(crop_factor=6, square=True))['native_size'] == [80, 80]


def test_no_lost_selection_when_square_impossible():
    mask = Image.new('L', (120, 80), 255)
    info = calculate_crop(mask, CropSettings(square=True, multiple_of=64))
    assert info['bounds'] == [0, 0, 120, 80]
    assert any('square' in warning for warning in info['warnings'])
    assert any('multiple' in warning for warning in info['warnings'])


def test_feather_at_exact_crop_boundary():
    source = Image.new('RGB', (100, 80))
    mask = Image.new('L', source.size)
    mask.paste(255, (20, 20, 80, 60))
    patch = Image.new('RGBA', (60, 40), 'white')
    _, effective = composite(source, patch, mask, [20, 20, 80, 60], feather=4)
    values = np.array(effective)
    assert 0 < values[40, 20] < 255
    assert values[40, 19] == 0
    assert values[40, 50] == 255


def test_color_corrects_edit_interior_and_excludes_semtransparent_context():
    source = Image.new('RGB', (64, 64), (120, 120, 120))
    patch = Image.new('RGBA', (64, 64), (100, 100, 100, 255))
    mask = Image.new('L', source.size)
    mask.paste(255, (20, 20, 44, 44))
    full, report = match_color(source, patch, mask, strength=1)
    half, _ = match_color(source, patch, mask, strength=.5)
    assert report['applied']
    assert full.getpixel((32, 32)) == (120, 120, 120, 255)
    assert half.getpixel((32, 32)) == (110, 110, 110, 255)
    patch.putalpha(100)
    _, report = match_color(source, patch, mask, strength=1)
    assert not report['applied']


def test_thin_image_morphology_and_seam_range():
    mask = Image.new('L', (1, 30))
    mask.putpixel((0, 15), 255)
    assert dilate(mask, 8).getbbox() == (0, 7, 1, 24)
    with pytest.raises(ValueError):
        seam_mask(mask, 129)
    assert seam_mask(mask, 0).getbbox() is None


def test_nonfinite_metadata_remains_json_serializable():
    image = Image.new('RGB', (8, 8))
    image.info['parameters'] = 'a picture\nSteps: inf, CFG scale: NaN, Seed: invalid'
    metadata = read_metadata(image)
    assert metadata['normalized']['cfg'] is None
    json.dumps(metadata, allow_nan=False)


def test_import_exif_rotation_applied_once():
    image = Image.new('RGB', (40, 20), 'red')
    exif = Image.Exif()
    exif[274] = 6
    data = io.BytesIO()
    image.save(data, format='JPEG', exif=exif)
    decoded, _ = decode_image(data.getvalue())
    assert decoded.size == (20, 40)
    aligned, _ = normalize_result(decoded, (20, 40))
    assert aligned.size == (20, 40)


def test_prompt_two_image_contract():
    prompt = build_prompt('Change the pupil color.', 'Soft watercolor rendering.')
    for word in ('Image 1', 'Image 2', 'semi-transparent', 'identity', 'gaze', 'expression', 'linework', 'lighting', 'Soft watercolor'):
        assert word in prompt
    assert 'Never reproduce the coral overlay' in prompt
    assert 'Return one clean' in prompt
    with pytest.raises(ValueError):
        build_prompt(' ')
    with pytest.raises(ValueError):
        build_prompt('x' * 4001)
