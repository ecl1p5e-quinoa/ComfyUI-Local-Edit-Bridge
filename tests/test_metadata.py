import io
import json

from PIL import Image, PngImagePlugin

from local_edit_helper.core.metadata import PROVENANCE_KEY, read_metadata, save_png


def png_bytes(image, chunks):
    buffer = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    for key, value in chunks.items():
        info.add_text(key, value)
    image.save(buffer, format="PNG", pnginfo=info)
    buffer.seek(0)
    return buffer


def test_a1111_parse():
    text = ("a landscape\nNegative prompt: blurry, low quality\n"
            "Steps: 20, Sampler: Euler, CFG scale: 7, Seed: 42, Model: dream.safetensors, Size: 512x512")
    metadata = read_metadata(Image.open(png_bytes(Image.new("RGB", (8, 8)), {"parameters": text})))
    normalized = metadata["normalized"]
    assert normalized["format"] == "a1111"
    assert normalized["prompt"] == "a landscape"
    assert normalized["negative_prompt"] == "blurry, low quality"
    assert normalized["sampler"] == "Euler"
    assert normalized["steps"] == 20 and normalized["cfg"] == 7.0 and normalized["seed"] == 42
    assert normalized["model"] == "dream.safetensors"
    assert metadata["raw"]["text"] == text
    json.dumps(metadata, allow_nan=False)


def test_comfy_graph_links():
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a red car", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["1", 1]}},
        "4": {"class_type": "KSampler", "inputs": {"seed": 7, "steps": 25, "cfg": 8.0,
                                                   "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0]}},
    }
    metadata = read_metadata(Image.open(png_bytes(Image.new("RGB", (8, 8)), {"prompt": json.dumps(graph)})))
    normalized = metadata["normalized"]
    assert normalized["format"] == "comfy"
    assert normalized["sampler"] == "KSampler"
    assert normalized["prompt"] == "a red car"
    assert normalized["negative_prompt"] == "blurry"
    assert normalized["model"] == "model.safetensors"
    assert normalized["steps"] == 25 and normalized["cfg"] == 8.0 and normalized["seed"] == 7
    json.dumps(metadata, allow_nan=False)


def test_malformed_metadata_is_graceful():
    broken = read_metadata(Image.open(png_bytes(Image.new("RGB", (8, 8)), {"prompt": "{not json"})))
    assert broken["normalized"]["format"] == "unknown"
    empty = read_metadata(Image.new("RGB", (8, 8)))
    assert empty["normalized"]["format"] == "unknown"
    json.dumps(broken, allow_nan=False)
    json.dumps(empty, allow_nan=False)


def test_save_png_round_trips_text_provenance_and_icc(tmp_path):
    icc = b"fake-icc-profile-bytes"
    source = Image.new("RGB", (8, 8), (1, 2, 3))
    source.info["icc_profile"] = icc
    opened = Image.open(png_bytes(source, {"parameters": "Steps: 4, Seed: 1"}))
    metadata = read_metadata(opened)
    assert metadata["raw"]["icc_profile"]
    path = tmp_path / "out.png"
    save_png(opened, path, metadata, provenance={"job_id": "abc", "crop": {"bounds": [0, 0, 8, 8]}})
    with Image.open(path) as result:
        result.load()
        assert result.info["parameters"] == "Steps: 4, Seed: 1"
        assert json.loads(result.info[PROVENANCE_KEY])["job_id"] == "abc"
        assert result.info["icc_profile"] == icc
        assert result.size == (8, 8)


def test_save_png_defaults_without_metadata(tmp_path):
    path = tmp_path / "plain.png"
    save_png(Image.new("L", (4, 4), 255), path, None)
    with Image.open(path) as result:
        result.load()
        assert result.size == (4, 4)
