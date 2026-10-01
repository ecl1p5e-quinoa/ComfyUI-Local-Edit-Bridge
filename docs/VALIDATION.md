# MVP validation — 2026-09-30

## Environment

- Active installation: Windows Portable ComfyUI, commit 0764232429b8cfb10b79b6f186c8cb23e0b22897.
- Runtime: embedded Python 3.13.9, Pillow 12.0.0, NumPy 2.2.6, SciPy 1.16.3, Torch 2.9.1+cu130.
- Installed frontend: 1.47.12.
- Project development environment: Python 3.13.9, Pillow 12.3.0, NumPy 2.5.3, SciPy 1.18.1,
  pytest 9.1.1, aiohttp 3.14.3. No Torch copy installed into the development environment.
- Runtime dependencies were already present; only the development environment was populated.

## Automated tests

Command from project directory:

    .venv\Scripts\python.exe -m pytest --confcutdir=tests tests -q

**68 passed in 2.21 seconds.** Coverage: all crop edges and corners, factor 1 and expansion,
clamping, minimum/multiple/square policies, empty/full/soft masks, inward feather at the exact
crop boundary, thin-image morphology, 0/255 seam bands, disabled/zero/full-strength color match,
flat channels, context opacity, import size/aspect/alpha/EXIF, PNG metadata and malformed values,
job states/revisions/reload/corruption, path checks, HTTP round trip and same-origin checks.

The same suite using the actual embedded ComfyUI interpreter and its image libraries, loading
only the test runner from the development environment: **68 passed in 2.48 seconds**.
Editable standalone package installation succeeded with pip install -e . --no-deps in the
development environment.

Frontend syntax checks passed for editor.js, canvas.js, api.js, extension/extension.js and
tools/browser_smoke.cjs. Git whitespace checks passed.

## Real ComfyUI and browser verification

Started a separate local ComfyUI process on 127.0.0.1:8190 with CPU mode, API nodes disabled,
only this custom node whitelisted, and user/input/output directories under ignored .test-output.
The plugin loads successfully and /object_info/GPTLocalEditJob reports IMAGE, MASK, STRING, STRING.
The extensions endpoint serves exactly one plugin extension script; standalone editor scripts
are intentionally outside WEB_DIRECTORY to avoid running them on the ComfyUI graph page.

Installed Edge + Playwright completed the UI round trip:

1. Upload deterministic 640×480 PNG with generation metadata.
2. Paint a mask using pointer events and change crop factor from 2.0 to 2.1.
3. Build an editable prompt and prepare the persistent export package.
4. Mark sent, import a deterministic modified crop, enable color matching and composite.
5. Preview before/after and seam mask, finalize, reload the page and reopen the same finalized job.

Browser result: **passed; 0 JavaScript page errors**. Source mask bbox [263,192,377,288];
export bounds [200,139,440,341]; clean crop 240×202. Job ID:
72528e0a307b456db9df953467add11a.

Saved-image verification:

- Original and final: 640×480 RGB.
- Preserved pixels outside nonzero mask: **298,242**.
- Maximum error outside the mask: **0** (bit-identical).
- Changed pixels: **6,230**.

After stopping and restarting the ComfyUI process, the same job reopened as FINALIZED.
An actual queued ComfyUI graph ran GPTLocalEditJob → SaveImage, and its seam MASK → MaskToImage
→ SaveImage. Execution status: **success**. The node-produced saved image again preserved outside-mask
pixels exactly. The full ComfyUI frontend created the helper node with both job_id and Open Editor
widgets, found the registered extension, and reported **0 JavaScript page errors**.

Screenshots: [editor](editor-roundtrip.png), [ComfyUI node](comfy-node.png).
Raw logs, reports and synthetic jobs remain in ignored .test-output for local inspection.

## Refinement example and scope of evidence

examples/seam_refinement.json uses existing ComfyUI nodes with explicit checkpoint and job-ID
placeholders. It restores decoded pixels through ImageCompositeMasked using the seam mask.
No diffusion model was loaded or downloaded, and the optional sampler workflow was not run.
No real ChatGPT image edit or ChatGPT website automation was used for validation.

## Performance check

1024×1024 mask, dilation radius 16: Pillow MaxFilter approximately 0.946 seconds;
SciPy maximum_filter approximately 0.0068 seconds. This is a local microbenchmark, not an
end-to-end latency guarantee. SciPy is an existing ComfyUI dependency.

## Review corrections

Independent review corrected strict mask sizing, opaque exterior-ring sampling, full-patch color
correction, binary seam strength, feather at exact crop bounds, EXIF double-rotation, nonfinite
metadata, exported-versus-native aspect validation and malformed-manifest handling.
Real startup validation corrected RouteTableDef registration. The browser harness now waits
for asynchronous state actions to finish before programmatically assigning file inputs.

## Five-step layout and GPT package update

- 79 Python tests pass in the development environment and embedded ComfyUI Python.
- Browser smoke verifies steps 1/2 side by side, settings inside the matching cards, steps 3/4/5 order, contain default, automatic ZIP download, step rework, and comparison slide/hold behavior.
- ZIP inspection confirms exactly 01-crop.png, 02-overlay.png, and prompt.txt.
- Repeated imports/reworks leave only current artifacts in the active job; one session-only undo checkpoint is stored temporarily outside the job directory.
- Desktop (1450px) and mobile (390px) layouts checked; no horizontal overflow. Canvas fits again when the layout resizes. Browser JavaScript errors: 0.
- The live user ComfyUI process was not restarted. Restart the backend and refresh the editor to activate updated routes and retention behavior.

## Preserve content on rework / open GPT folder

- Rework preserves mask pixels, crop settings, prompt/request/context, fitting policy and blend settings. Only dependent results are invalidated; import rework retains the existing returned image.
- Prepare now opens gpt-handoff in the local file manager. It contains exactly 01-crop.png, 02-overlay.png and prompt.txt. ZIP routes and download UI were removed.
- Folder opening uses a same-origin POST, a loopback client check, revision validation and a server-owned path. No caller-supplied filesystem path is accepted.
- 80 Python tests pass; browser flow passes with zero JavaScript errors. The browser suite stubs the native folder opener, and the actual Windows opener was separately invoked successfully on the verified three-file test folder.
