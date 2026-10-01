"""Builds an inspectable edit instruction that uses a clean crop and an overlay location guide."""

MAX_REQUEST = 4000
MAX_CONTEXT = 4000
MAX_PROMPT = 16000

TEMPLATE = (
    "Use the two images attached with these instructions. "
    "Image 1 (01-crop.png) is the clean crop: edit this "
    "image directly. Image 2 (02-overlay.png) is the same crop with a semi-transparent coral overlay "
    "marking the region to edit. Use Image 2 only as a location reference, not as the output "
    "or as a color/style reference. The overlay is a visual guide, not a separate mask input. "
    "Apply the requested change only within the highlighted region; preserve everything "
    "outside it. Never reproduce the coral overlay, guide markings, or tint in the result. "
    "Preserve composition, pose, character identity, gaze and expression unless the request "
    "explicitly changes them. Preserve rendering style, linework, texture, local lighting "
    "and color relationships. Do not redesign unchanged content or add irrelevant details "
    "or noise. Do not move, rescale, rotate, add borders or crop the image. Return one clean "
    "edited version of Image 1 with the same crop framing, aspect ratio and resolution."
)


def _text(value, name, limit, required):
    if not isinstance(value, str):
        raise ValueError(name + " must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(name + " cannot be empty.")
    if len(value) > limit:
        raise ValueError(f"{name} must be at most {limit} characters.")
    return value


def build_prompt(request, context=""):
    request = _text(request, "Request", MAX_REQUEST, True)
    context = _text(context, "Context", MAX_CONTEXT, False)
    parts = [TEMPLATE, "", "Edit request:", request]
    if context:
        parts += ["", "Selected context to consider:", context]
    prompt = "\n".join(parts)
    if len(prompt) > MAX_PROMPT:
        raise ValueError(f"The prompt must be at most {MAX_PROMPT} characters.")
    return prompt
