"""Seam band between the edit mask edges. Square structuring element, native pixels."""
from PIL import Image, ImageChops

from .mask import _radius, dilate, erode


def seam_mask(mask, width):
    width = _radius(width)
    if mask.mode != "L":
        mask = mask.convert("L")
    binary = mask.point(lambda value: 255 if value else 0)
    if width == 0 or binary.getbbox() is None:
        return Image.new("L", mask.size, 0)
    return ImageChops.subtract(dilate(binary, width), erode(binary, width))
