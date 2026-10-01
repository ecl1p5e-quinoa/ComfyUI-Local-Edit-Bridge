"""Mask normalization and morphology. Masks are L images: 0 preserve, 255 edit."""
import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter
from scipy.ndimage import maximum_filter, minimum_filter


def _radius(radius):
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise ValueError("Radius must be a number.")
    if not math.isfinite(radius) or not 0 <= radius <= 128 or int(radius) != radius:
        raise ValueError("Radius must be an integer between 0 and 128.")
    return int(radius)


def normalize_mask(mask, size):
    if mask.mode != "L":
        mask = mask.convert("L")
    if mask.size != tuple(size):
        raise ValueError("Mask dimensions must exactly match the source image.")
    return mask


def dilate(mask, radius):
    radius = _radius(radius)
    if radius == 0:
        return mask.copy()
    return Image.fromarray(maximum_filter(np.asarray(mask), size=2 * radius + 1, mode="constant", cval=0))


def erode(mask, radius):
    radius = _radius(radius)
    if radius == 0:
        return mask.copy()
    return Image.fromarray(minimum_filter(np.asarray(mask), size=2 * radius + 1, mode="constant", cval=0))


def feather_mask(mask, radius):
    radius = _radius(radius)
    if radius == 0:
        return mask.copy()
    return ImageChops.multiply(mask.filter(ImageFilter.GaussianBlur(radius)), mask)
