"""Textual PNG metadata: raw chunks, a normalized summary and safe re-embedding."""
import base64
import json
import math

from PIL import PngImagePlugin

PROVENANCE_KEY = "gpt-local-edit"


def _text_chunks(image):
    chunks = {}
    for source in (getattr(image, "text", None), getattr(image, "info", None)):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, str) and key not in chunks:
                    chunks[key] = value
    return chunks


def _load_json(text):
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _as_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _settings_pairs(line):
    pairs = {}
    for part in line.split(", "):
        if ":" in part:
            key, _, value = part.partition(":")
            pairs[key.strip()] = value.strip()
    return pairs


def _parse_a1111(text):
    result = {"format": "a1111", "prompt": "", "negative_prompt": "", "sampler": None,
              "steps": None, "cfg": None, "seed": None, "model": None, "size": None}
    lines = text.splitlines()
    settings_index = None
    for index, line in enumerate(lines):
        if ":" in line and any(token in line for token in ("Steps:", "Sampler:", "CFG scale:")):
            settings_index = index
            break
    body = lines if settings_index is None else lines[:settings_index]
    settings = _settings_pairs("" if settings_index is None else lines[settings_index])
    positive, negative = [], []
    target = positive
    for line in body:
        if line.startswith("Negative prompt:"):
            target = negative
            negative.append(line[len("Negative prompt:"):].strip())
            continue
        target.append(line)
    result["prompt"] = "\n".join(positive).strip()
    result["negative_prompt"] = "\n".join(negative).strip()
    result["sampler"] = settings.get("Sampler")
    result["scheduler"] = settings.get("Schedule type") or settings.get("Scheduler")
    result["steps"] = _as_int(settings.get("Steps"))
    result["cfg"] = _as_float(settings.get("CFG scale"))
    result["seed"] = _as_int(settings.get("Seed"))
    result["model"] = settings.get("Model") or settings.get("Model hash")
    result["size"] = settings.get("Size")
    return result


def _is_sampler(class_type):
    return isinstance(class_type, str) and "sampler" in class_type.lower()


def _follow(nodes, link):
    node_id = None
    if isinstance(link, (list, tuple)) and link:
        node_id = link[0]
    elif isinstance(link, dict):
        node_id = link.get("node_id", link.get("node"))
    if node_id is None:
        return None
    return nodes.get(str(node_id))


def _resolve_text(nodes, link, depth=0):
    if depth > 8:
        return ""
    node = _follow(nodes, link)
    if node is None:
        return ""
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
    text = inputs.get("text")
    if isinstance(text, str):
        return text
    for key in ("conditioning", "conditioning_1", "conditioning_2"):
        resolved = _resolve_text(nodes, inputs.get(key), depth + 1)
        if resolved:
            return resolved
    return ""


def _resolve_model(nodes, link):
    node = _follow(nodes, link)
    seen = 0
    while node is not None and seen < 16:
        seen += 1
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        name = inputs.get("ckpt_name") or inputs.get("unet_name")
        if isinstance(name, str):
            return name
        node = _follow(nodes, inputs.get("model"))
    return None


def _parse_comfy(chunks):
    result = {"format": "comfy", "prompt": "", "negative_prompt": "", "sampler": None,
              "samplers": [], "steps": None, "cfg": None, "seed": None, "model": None}
    graph = _load_json(chunks.get("prompt"))
    if not isinstance(graph, dict):
        result["format"] = "unknown"
        return result
    nodes = {key: value for key, value in graph.items() if isinstance(value, dict)}
    samplers = [(key, node) for key, node in nodes.items() if _is_sampler(node.get("class_type"))]
    result["samplers"] = [node.get("class_type") for _, node in samplers]
    if not samplers:
        return result
    _, node = samplers[0]
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
    result["sampler"] = inputs.get("sampler_name") or node.get("class_type")
    result["scheduler"] = inputs.get("scheduler")
    result["steps"] = _as_int(inputs.get("steps"))
    result["cfg"] = _as_float(inputs.get("cfg"))
    result["seed"] = _as_int(inputs.get("seed", inputs.get("noise_seed")))
    result["prompt"] = _resolve_text(nodes, inputs.get("positive"))
    result["negative_prompt"] = _resolve_text(nodes, inputs.get("negative"))
    result["model"] = _resolve_model(nodes, inputs.get("model"))
    return result


def read_metadata(image):
    chunks = _text_chunks(image)
    raw = {"text": "", "chunks": chunks}
    info = getattr(image, "info", None)
    icc = info.get("icc_profile") if isinstance(info, dict) else None
    if icc:
        raw["icc_profile"] = base64.b64encode(icc).decode("ascii")
    if "parameters" in chunks:
        raw["text"] = chunks["parameters"]
        normalized = _parse_a1111(chunks["parameters"])
    elif "prompt" in chunks:
        raw["text"] = chunks["prompt"]
        normalized = _parse_comfy(chunks)
    else:
        raw["text"] = "\n".join(f"{key}: {value}" for key, value in chunks.items())
        normalized = {"format": "unknown"}
    normalized["dimensions"] = list(image.size)
    return {"raw": raw, "normalized": normalized}


def _add_text(pnginfo, name, value):
    try:
        pnginfo.add_text(name, value)
    except UnicodeEncodeError:
        pnginfo.add_itxt(name, value)


def save_png(image, path, metadata, provenance=None):
    metadata = metadata if isinstance(metadata, dict) else {}
    raw = metadata.get("raw") if isinstance(metadata.get("raw"), dict) else {}
    chunks = raw.get("chunks")
    pnginfo = PngImagePlugin.PngInfo()
    if isinstance(chunks, dict) and chunks:
        for name, value in chunks.items():
            if isinstance(value, str):
                _add_text(pnginfo, str(name), value)
    elif isinstance(raw.get("text"), str) and raw["text"]:
        _add_text(pnginfo, "parameters", raw["text"])
    if provenance is not None:
        _add_text(pnginfo, PROVENANCE_KEY, json.dumps(provenance, ensure_ascii=False, allow_nan=False))
    icc = image.info.get("icc_profile") if isinstance(image.info, dict) else None
    if not icc and isinstance(raw.get("icc_profile"), str):
        try:
            icc = base64.b64decode(raw["icc_profile"])
        except (ValueError, TypeError):
            icc = None
    options = {"format": "PNG", "pnginfo": pnginfo}
    if icc:
        options["icc_profile"] = icc
    image.save(path, **options)
