"""Conservative ring statistics match. Works on crop-sized source/patch/mask regions."""
import numpy as np
from PIL import Image, ImageChops

from .mask import dilate

MIN_SAMPLES = 64
ALPHA_FLOOR = 254
SCALE_LOW = 0.8
SCALE_HIGH = 1.25
MEAN_LIMIT = 32.0 / 255.0
EPSILON = 1e-6


def match_color(source, patch, mask, enabled=True, strength=0.5, ring_width=16):
    source = source.convert("RGB")
    patch = patch.convert("RGBA")
    mask = mask.convert("L")
    if source.size != patch.size or mask.size != patch.size:
        raise ValueError("Color match inputs must share the crop size.")
    if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not 0 <= strength <= 1:
        raise ValueError("Color strength must be between 0 and 1.")
    report = {"enabled": bool(enabled), "strength": float(strength), "applied": False,
              "samples": 0, "corrected": 0, "scale": [1.0, 1.0, 1.0], "offset": [0.0, 0.0, 0.0]}
    if not enabled or strength == 0:
        return patch.copy(), report
    binary = mask.point(lambda value: 255 if value else 0)
    ring = ImageChops.subtract(dilate(binary, ring_width), binary)
    patch_pixels = np.asarray(patch, dtype=np.float32) / 255.0
    source_pixels = np.asarray(source, dtype=np.float32) / 255.0
    valid = (np.asarray(ring) > 0) & (patch_pixels[..., 3] >= ALPHA_FLOOR / 255.0)
    samples = int(valid.sum())
    report["samples"] = samples
    if samples < MIN_SAMPLES:
        return patch.copy(), report
    out = patch_pixels.copy()
    scales, offsets = [], []
    for channel in range(3):
        source_channel = source_pixels[valid, channel]
        patch_channel = patch_pixels[valid, channel]
        source_mean = float(source_channel.mean())
        patch_mean = float(patch_channel.mean())
        source_std = float(source_channel.std())
        patch_std = float(patch_channel.std())
        offset = float(np.clip(source_mean - patch_mean, -MEAN_LIMIT, MEAN_LIMIT))
        if source_std <= EPSILON or patch_std <= EPSILON:
            scale = 1.0
        else:
            scale = float(np.clip(source_std / patch_std, SCALE_LOW, SCALE_HIGH))
        values = patch_pixels[..., channel]
        corrected = np.clip((values - patch_mean) * scale + patch_mean + offset, 0.0, 1.0)
        out[..., channel] = values + strength * (corrected - values)
        scales.append(round(scale, 6))
        offsets.append(round(offset, 6))
    report.update(applied=True, corrected=int((patch_pixels[..., 3] > 0).sum()), scale=scales, offset=offsets)
    pixels = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(pixels), report
