# Prior-art audit

Audit started 2026-09-30 before implementation. Sources inspected directly, not only READMEs.
The source-level worker supplement below was independently reviewed.

| Repository | License evidence | Source inspected | Reuse / decision |
| --- | --- | --- | --- |
| [InpaintCanvas](https://github.com/DenRakEiw/ComfyUI-InpaintCanvas) | LICENSE: GPL-3.0 | `nodes.py`: `_fit_image`, `_color_match`, `_align_patch`, `_composite_mask`; `js/inpaint_compositor.js`; `__init__.py` | Conceptual reference only, no copied/adapted GPL implementation. Weighted context statistics and cautious alignment are useful product precedents; layered WebGL editor is beyond this MVP. |
| [CropStitch-NB2](https://github.com/amortegui84/comfyui-inpaint-cropstitch-nb2) | LICENSE declares Apache-2.0 for original and modifications, abbreviated text; GitHub reports NOASSERTION | `nodes.py`: `SmartMaskCrop`, `SmartObjectIsolateCrop`, `InpaintCropNB2` | Clean crop / preserved context already solved. Do not import provider APIs, automatic dependency installation, or fixed model resolutions. No code copied. |
| [NKD Basic Tools](https://github.com/Nekodificador/ComfyUI-NKD-Basic-Tools) | root LICENSE: MIT; nested LivePortrait license separate | `nkd_crop_stitch.py`: `NKDCropData`, `NKDInpaintCrop`, `NKDInpaintStitch`, differential diffusion wrapper | Crop-data ownership and explicit stitch contract are useful references. Prefer existing ComfyUI diffusion nodes over copying sampler/model wrapping. Core must avoid Torch dependency. |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | GPL-3.0 | local `nodes.py:load_custom_node`, `server.py:add_routes`, `custom_nodes/example_node.py.example` | Integrate public node/route interfaces at adapter boundary. V1 registration remains supported alongside V3. No core code copied. |
| [ComfyUI frontend](https://github.com/Comfy-Org/ComfyUI_frontend) | See upstream LICENSE | `src/types/comfy.ts`; official extension hooks documentation | `WEB_DIRECTORY`, `app.registerExtension`, `nodeCreated`, ordinary node button; direct editor route is independent of graph rendering. |

Official interface documentation: [JavaScript extensions](https://docs.comfy.org/custom-nodes/js/javascript_overview).

## What is already solved

Painting, context cropping, alpha stitch, color statistics and diffusion are established tools.
Use Canvas 2D for painting, Pillow for resampling/filtering/PNG, NumPy for bounded statistics,
and installed ComfyUI nodes for diffusion. No vendor code is required for these small operations.

## Project-specific glue

Persistent manual external-editor jobs, inspectable prompt preparation, exact backend crop preview,
frozen handoff assets, explicit import fitting policy and a seam-only finishing handoff. This is
not a new crop/stitch algorithm. Strong pixel preservation and standalone core determine the design.

No third-party source has been copied. Reference-only audit does not relicense upstream projects;
distribution of a combined ComfyUI system retains its own applicable upstream obligations.

## Worker source audit supplement (2026-09-30)

Offline copies under `.audit/` were read directly (revision strings are the exact pins recorded in
`*.revision.txt`). All findings are evidence for the interfaces below; no upstream code was copied.

| Source (pinned revision) | License evidence | File / function evidence | Algorithm observed | Decision |
| --- | --- | --- | --- | --- |
| `lquesada/ComfyUI-Inpaint-CropAndStitch` `8584b08d851762965df898b421a39075fc5357ae` | `.audit` `LICENSE` is the full **GPL-3.0** text and `revision.txt` says `GPL-3.0`; the source file has no permissive header | `inpaint_cropandstitch.py`: `ProcessorLogic.findcontextarea_m` (L190), `growcontextarea_m` (L201), `pad_to_multiple` (L175/500), `crop_magic_im` (L218/719), `stitch_magic_im` (L221); `_get_pil_resampling` (L349) | Mask bbox, context grow to a target aspect ratio with center-then-clamp placement, ceil-to-multiple padding, crop/stitch with blend `mask*inpaint + (1-mask)*canvas` | Reference for crop geometry and blend form only. **GPL-3.0**: do not copy or adapt; our crop/stitch is an independent Pillow implementation. |
| `amortegui84/comfyui-inpaint-cropstitch-nb2` `2d5fce30c6a79509601d995325778b4bd115732b` | `revision.txt` reports `NOASSERTION`; `LICENSE` is an **abbreviated Apache-2.0** text that states this is a fork of lquesada "Licensed under the Apache License, Version 2.0" | `nodes.py`: `ProcessorLogic` (L485), `CPUProcessorLogic` (L595), `GPUProcessorLogic` (L933), `InpaintCropNB2` (L2637), `InpaintStitchNB2` (L2792, alpha multiplied into feather mask) | Fixed target resolution for one provider model, smoothstep edge feather, optional alpha blend | **License provenance needs care**: the inspected current upstream is GPL-3.0 while this fork declares Apache-2.0; its historical base revision was not established. Reference only, no code copied, and no vendor provider/API behavior adopted. |
| `DenRakEiw/ComfyUI-InpaintCanvas` `efee88f1af2267b6512df9da5db7793b25f19eb7` | `.audit` `LICENSE` is the full **GPL-3.0** text; `revision.txt` says `GPL-3.0` | `nodes.py`: `_fit_image` (L101, aspect-fit + border-color pad), `_border_color` (L94), `_dilate_mask` (L271, separable max), `_erode_mask` (L286 as `1-dilate(1-mask)`), `_blur_mask` (L225, PIL GaussianBlur), `_selection_bbox` (L489), `_fit_span_to_multiple` (L502), `_gauss_np` (L307), `_color_match` (L389, weighted ring mean/std with `total<64` guard), `_align_patch` (L411, optional OpenCV ECC) | Square max/min mask morphology, Gaussian mask blur, ring-weighted per-channel mean/std color shift with a 64-sample floor, optional ECC registration | Reference for ring statistics, sample floor and square structuring elements. **GPL-3.0**: no code copied; our erosion uses explicit black padding instead of `1-dilate(1-mask)`, and v0.1 has no auto registration. |
| `Nekodificador/ComfyUI-NKD-Basic-Tools` `85deb827645cbc6e4462a0020069b7918e8e7eb6` | root `LICENSE` is MIT (nested LivePortrait license is separate and unused) | `nkd_crop_stitch.py`: `NKDCropData` (L59), `NKDInpaintCrop.execute` (L178), `NKDInpaintStitch.execute` (L292), `_crop_by_mask`, `_mask_grow`, `_uncrop` | Explicit crop-data record carried from crop to stitch: background, crop box, original size, region mask; feather applied on uncrop | Confirms our bounds/effective-mask ownership and the "crop returns info, composite consumes bounds" split. No code copied; core stays Torch-free. |
| `Comfy-Org/ComfyUI_frontend` `934af0705efb127c9c9530e98a5531bff88aba05` | `.audit` `LICENSE` full **GPL-3.0**; `revision.txt` says `GPL-3.0` | `src/types/comfy.ts`: `ComfyExtension` hooks (`setup`, `beforeRegisterNodeDef`, `nodeCreated`, `getCanvasMenuItems`, ...); `docs/extensions/core.md`: registration via `app.registerExtension()`, hook-driven, non-intrusive | Extension contract for a node button and a graph-independent editor entry | Interface reference only for the later web layer; no frontend code copied. |

The primary agent inspected the installed ComfyUI source directly at commit
`0764232429b8cfb10b79b6f186c8cb23e0b22897`, including `nodes.py:load_custom_node`,
`server.py:add_routes`, `comfy_extras/nodes_mask.py:ImageCompositeMasked`, and the official example.
Local frontend package: 1.47.12. Its app/api shims and the published extension type agree on the hooks used.

The current upstream/fork license discrepancy does not establish historical licensing of the fork's
base revision. Historical provenance was not established; neither implementation is incorporated.
SciPy maximum/minimum filters were selected during validation over slow Pillow rank filters, reusing
an existing installed dependency rather than implementing a custom morphology algorithm.
