"""Mask-feathered compositing. Outside the supplied nonzero mask source stays bit-identical."""
from PIL import Image, ImageChops

from .mask import feather_mask


def _bounds(bounds, size):
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ValueError("Bounds must be four integers.")
    if any(type(value) is not int for value in bounds):
        raise ValueError("Bounds must be four integers.")
    left, top, right, bottom = bounds
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("Bounds are outside the source image.")
    return left, top, right, bottom


def composite(source, patch, mask, bounds, feather=8):
    if source.mode not in ("RGB", "RGBA"):
        raise ValueError("Composite source must be RGB or RGBA.")
    patch = patch.convert("RGBA")
    mask = mask.convert("L")
    if mask.size != source.size:
        raise ValueError("The composite mask must match the source image size.")
    region = _bounds(bounds, source.size)
    if patch.size != (region[2] - region[0], region[3] - region[1]):
        raise ValueError("The returned patch must match the crop bounds.")
    coverage = ImageChops.multiply(feather_mask(mask, feather).crop(region), patch.getchannel("A"))
    effective = Image.new("L", source.size, 0)
    effective.paste(coverage, region)
    blended = Image.composite(patch.convert("RGB"), source.crop(region).convert("RGB"), coverage)
    output = source.copy()
    if source.mode == "RGBA":
        blended = blended.convert("RGBA")
        blended.putalpha(source.getchannel("A").crop(region))
    output.paste(blended, region)
    return output, effective
