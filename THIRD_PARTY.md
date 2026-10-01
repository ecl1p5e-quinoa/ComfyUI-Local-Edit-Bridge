# Third-party references and dependencies

No upstream application code is incorporated or vendored as a runtime dependency. All plugin code
is original glue built on library APIs. docs/PRIOR_ART.md records pinned source files inspected.
Ignored .audit snapshots are development reference material and are not part of the distributable plugin.

- DenRakEiw/ComfyUI-InpaintCanvas — GPL-3.0. Conceptual reference for mask UI, crop context,
  context-ring matching and cautious registration. No GPL implementation is included.
- lquesada/ComfyUI-Inpaint-CropAndStitch — pinned current LICENSE is GPL-3.0. Crop/stitch concepts only.
- amortegui84/comfyui-inpaint-cropstitch-nb2 — its abbreviated license declares Apache-2.0 while
  the inspected current upstream declares GPL-3.0. Historical fork provenance was not established;
  no code is reused and no conclusion about historical relicensing is implied.
- Nekodificador/ComfyUI-NKD-Basic-Tools — root MIT; separate nested component licenses exist.
  Reference for mask painting and crop-data/stitch contracts. No source included.
- ComfyUI and ComfyUI_frontend — GPL-3.0. Public extension/node interfaces are integrated;
  installed core nodes own diffusion. This MIT notice does not relicense ComfyUI or a combined distribution.

Runtime libraries are installed separately: Pillow (HPND/PIL license), NumPy (BSD-3-Clause),
SciPy (BSD-3-Clause); ComfyUI supplies aiohttp and Torch at the adapter boundary.
Each dependency retains its distributed license notices.
