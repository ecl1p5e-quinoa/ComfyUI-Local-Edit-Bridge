# MVP completion report

## What was built

A complete local manual semantic-edit round trip: source upload/drop and PNG metadata; brush/eraser,
undo/redo, zoom/pan; shared-backend crop preview; editable prompt; frozen export package; persistent
job states; returned-image upload/drop; explicit aspect fitting; optional context-ring color match;
inward feathered composite; narrow seam mask; full-size PNG export and job reopen.

## Project path

G:/Comfy/ComfyUI_windows_portable_nvidia_NEW/ComfyUI_windows_portable/ComfyUI/custom_nodes/comfyui-gpt-local-edit-helper

This is a new independent Git repository. The requested name was available. No existing project or
ComfyUI core file was modified. The original installation's pre-existing changes were preserved.
Implementation is local and uncommitted; nothing was published or pushed.

## Architecture

- core: reusable Pillow/NumPy/SciPy processing and disk manifests, no ComfyUI/Torch imports.
- prompt: bounded preservation template plus optional selected context.
- bridge: manual prepare/import/composite/finalize orchestration.
- comfy: same-origin local routes, configured output root, one job-loading node.
- web: plain ES-module Canvas editor; one separately registered frontend extension.
- .venv: Python 3.13.9 development environment; runtime remains ComfyUI's embedded Python.

## Prior art and licenses

Actual source and licenses were inspected for the three required repositories, original
CropAndStitch, official frontend extension types and local ComfyUI registration/route/node code.
See [PRIOR_ART.md](PRIOR_ART.md) for pinned commits and specific functions.

InpaintCanvas, current original CropAndStitch, ComfyUI and its frontend: GPL-3.0.
NKD Basic Tools root: MIT. NB2's abbreviated license declares Apache-2.0, differing from the
inspected current upstream; historical fork provenance was not established. All were used as
conceptual/interface references. No upstream application code is incorporated into this MIT plugin.

Reused library functionality: Pillow image decoding/resizing/PNG/feathering; NumPy statistics;
SciPy optimized morphology; Canvas painting; ComfyUI VAE, sampling and image-composite nodes.
Existing model/sampling infrastructure was deliberately reused instead of implementing a diffusion
engine or copying another editor's model wrappers. A layered WebGL editor and ECC registration
were not copied from the GPL reference implementation.

DeepSeek performed the offline source audit and initial pure imaging/test implementation.
The primary agent owned architecture, persistence/routes/UI, independent code review, corrections,
integration and final validation. Worker sandbox controls were retained.

## Files added

- Root: __init__.py, pyproject.toml, requirements.txt, LICENSE, THIRD_PARTY.md, README.md, .gitignore.
- core: crop.py, mask.py, alignment.py, color_match.py, composite.py, seam.py, metadata.py, jobs.py.
- prompt/builder.py; bridge/manual.py; comfy/nodes.py, routes.py, integration.py; package initializers.
- web: index.html, editor.css, editor.js, canvas.js, api.js, extension/extension.js.
- tests: conftest.py, test_imaging.py, test_metadata.py, test_jobs.py, test_routes.py, test_regressions.py.
- tools: deterministic fixture generator, browser round-trip and runtime-node verification scripts.
- examples/seam_refinement.json.
- docs: prior-art audit, design, validation, this report and two verified screenshots.
- Ignored development-only directories: .venv, .devtools, .audit, .test-output and test scratch data.

## Tests and exact results

- Development Python: **68 passed in 2.21 s**.
- Actual embedded ComfyUI Python with its installed image libraries: **68 passed in 2.48 s**.
- Frontend syntax checks and Git whitespace checks: passed.
- Real ComfyUI startup: plugin registered successfully; node outputs IMAGE/MASK/STRING/STRING.
- Full Edge browser round trip and reload: passed, **0 JavaScript errors**.
- Full ComfyUI graph frontend: Open Editor button and extension registered, **0 JavaScript errors**.
- Real queued GPTLocalEditJob → SaveImage and seam → MaskToImage → SaveImage: success.
- Process restart: persisted job reopened as FINALIZED.
- Final image: 640×480; **298,242 outside-mask pixels preserved exactly, maximum error 0**;
  6,230 pixels changed inside the permitted region.
- Standalone editable package installation: success.

See [VALIDATION.md](VALIDATION.md) for commands, runtime versions, test scope and evidence.
No real ChatGPT interaction or diffusion model execution was needed for the synthetic round trip.

## Manual workflow

Restart normal ComfyUI, add GPT Local Edit Helper, and click Open Editor (or use its Tools menu entry).
Load PNG → paint mask → adjust crop → build/review prompt → Prepare for GPT → manually send crop.png
and prompt to ChatGPT → save/import returned image → optionally color-match → composite → inspect seam
→ finalize/save. Copy the job ID into the loader node for optional graph-based refinement.

## Known limitations

No automatic spatial alignment, no ChatGPT automation/API, no one-click sampler invocation, no EXE.
8-bit still-image workflow; 32 MiB/24-million-pixel source limit; metadata extraction is best-effort.
Color arithmetic is in stored RGB values, not a fully color-managed linear pipeline. Undo history is
session-only and bounded by memory. Prompt edits are persisted at Prepare; unfinished prompt text
can be lost on reload. Earlier imported/processed files remain in the job directory.
The example refinement workflow requires the user's own model and has not been sampled with one.

## v0.2 and next milestone

**Yes: a configurable one-click ComfyUI seam-refinement handoff is a good next milestone**, after
validating the example on the user's chosen model. Keep sampling/model management in existing nodes,
retain final seam-only restoration, and expose model-appropriate denoise instead of a universal preset.
Reliable opt-in context alignment, candidate comparison and persistent prompt drafts should follow.
