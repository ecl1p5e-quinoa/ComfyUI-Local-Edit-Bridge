"""Import normalization. No registration: strict aspect check or proportional contain."""
from PIL import Image, ImageOps

TOLERANCE = 0.02


def _target_size(size):
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ValueError("Target size must be a pair of integers.")
    width, height = size
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (width, height)):
        raise ValueError("Target size must be a pair of positive integers.")
    return int(width), int(height)


def normalize_result(result, size, policy="strict"):
    if policy not in ("strict", "contain"):
        raise ValueError("Unknown import policy.")
    target = _target_size(size)
    result = ImageOps.exif_transpose(result).convert("RGBA")
    source = result.size
    warnings = []
    if policy == "strict":
        relative = abs(source[0] / source[1] - target[0] / target[1]) / (target[0] / target[1])
        if relative > TOLERANCE:
            raise ValueError("The returned image aspect ratio does not match the crop.")
        if source != target:
            result = result.resize(target, Image.LANCZOS)
            warnings.append("The returned image was resized to the crop size.")
        return result, warnings
    scale = min(target[0] / source[0], target[1] / source[1])
    fitted = (max(1, round(source[0] * scale)), max(1, round(source[1] * scale)))
    if fitted != source:
        result = result.resize(fitted, Image.LANCZOS)
    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    canvas.paste(result, ((target[0] - fitted[0]) // 2, (target[1] - fitted[1]) // 2))
    if fitted != target:
        warnings.append("The returned image was fitted with transparent padding.")
    return canvas, warnings
