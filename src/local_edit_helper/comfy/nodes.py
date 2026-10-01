import json

import numpy as np
import torch
from PIL import Image

from .integration import store


class GPTLocalEditJob:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job_id": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING")
    RETURN_NAMES = ("composited_image", "seam_mask", "prompt", "job_metadata")
    FUNCTION = "load"
    CATEGORY = "image/local edit"
    DESCRIPTION = "Open Editor to prepare a manual external edit. Load the completed job for optional seam refinement."

    @classmethod
    def IS_CHANGED(cls, job_id):
        return store.read(job_id)["revision"]

    def load(self, job_id):
        with store.lock:
            job = store.read(job_id)
            if job["state"] not in {"COMPOSITED", "FINALIZED"}:
                raise ValueError("Import a result and composite it in Open Editor first.")
            with Image.open(store.artifact(job_id, job["files"]["composite"])) as source:
                image = torch.from_numpy(np.array(source.convert("RGB"), dtype=np.float32) / 255.0).unsqueeze(0)
            with Image.open(store.artifact(job_id, job["files"]["seam"])) as source:
                mask = torch.from_numpy(np.array(source.convert("L"), dtype=np.float32) / 255.0).unsqueeze(0)
            return image, mask, job["prompt"], json.dumps(job, ensure_ascii=False)


NODE_CLASS_MAPPINGS = {"GPTLocalEditJob": GPTLocalEditJob}
NODE_DISPLAY_NAME_MAPPINGS = {"GPTLocalEditJob": "Local Edit Bridge"}
