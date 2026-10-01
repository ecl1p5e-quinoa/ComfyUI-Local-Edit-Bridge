"""Crop geometry. Bounds are [left, top, right, bottom] with the right/bottom exclusive."""
import math
from dataclasses import dataclass

from PIL import Image

POLICIES = ("native", "limit_1024")
LONG_EDGE = 1024


@dataclass(frozen=True)
class CropSettings:
    crop_factor: float = 2.0
    min_size: int = 64
    multiple_of: int = 1
    square: bool = False
    output_policy: str = "native"


def _validate(settings):
    if not isinstance(settings, CropSettings):
        raise ValueError("Crop settings must be a CropSettings instance.")
    if isinstance(settings.crop_factor, bool) or not isinstance(settings.crop_factor, (int, float)) \
            or not math.isfinite(settings.crop_factor) or settings.crop_factor < 1:
        raise ValueError("Crop factor must be a finite number of at least 1.")
    if type(settings.min_size) is not int or settings.min_size < 1:
        raise ValueError("Minimum size must be a positive integer.")
    if type(settings.multiple_of) is not int or settings.multiple_of < 1:
        raise ValueError("Size multiple must be a positive integer.")
    if type(settings.square) is not bool:
        raise ValueError("Square must be true or false.")
    if settings.output_policy not in POLICIES:
        raise ValueError("Unknown output policy.")


def _round_up(value, multiple):
    return ((value + multiple - 1) // multiple) * multiple


def _export_size(native, policy):
    longest = max(native)
    if policy != "limit_1024" or longest <= LONG_EDGE:
        return list(native)
    scale = LONG_EDGE / longest
    return [max(1, round(native[0] * scale)), max(1, round(native[1] * scale))]


def calculate_crop(mask, settings):
    _validate(settings)
    box = mask.getbbox()
    if box is None:
        raise ValueError("Paint an edit mask before cropping.")
    left, top, right, bottom = box
    warnings = []
    width = int(math.ceil((right - left) * settings.crop_factor))
    height = int(math.ceil((bottom - top) * settings.crop_factor))
    width = _round_up(max(width, settings.min_size), settings.multiple_of)
    height = _round_up(max(height, settings.min_size), settings.multiple_of)
    if settings.square:
        width = height = max(width, height)
        available = min(mask.size)
        if max(right - left, bottom - top) <= available and width > available:
            width = height = available
            warnings.append("The square crop was limited by the shorter image edge.")
    if width > mask.width or height > mask.height:
        warnings.append("The requested crop is larger than the image and was clamped to its edges.")
    width = min(width, mask.width)
    height = min(height, mask.height)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    crop_left = max(0, min(int(round(center_x - width / 2)), left, mask.width - width))
    crop_top = max(0, min(int(round(center_y - height / 2)), top, mask.height - height))
    if width % settings.multiple_of or height % settings.multiple_of:
        warnings.append("The clamped crop could not keep the requested size multiple.")
    if settings.square and width != height:
        warnings.append("The clamped crop could not remain square.")
    native = [width, height]
    export = _export_size(native, settings.output_policy)
    if export != native:
        warnings.append("The exported crop was scaled down to a 1024 pixel long edge.")
    return {"bbox": [left, top, right, bottom], "bounds": [crop_left, crop_top, crop_left + width, crop_top + height],
            "native_size": native, "export_size": export, "warnings": warnings}


def make_crop(image, mask, settings):
    if image.mode not in ("RGB", "RGBA") or mask.mode != "L":
        raise ValueError("Crop needs an RGB/RGBA source and an L mask.")
    if mask.size != image.size:
        raise ValueError("The mask must match the source image size.")
    info = calculate_crop(mask, settings)
    bounds = tuple(info["bounds"])
    crop = image.crop(bounds).convert("RGB")
    crop_mask = mask.crop(bounds)
    if info["export_size"] != info["native_size"]:
        size = tuple(info["export_size"])
        crop = crop.resize(size, Image.LANCZOS)
        crop_mask = crop_mask.resize(size, Image.NEAREST)
    return crop, crop_mask, info
