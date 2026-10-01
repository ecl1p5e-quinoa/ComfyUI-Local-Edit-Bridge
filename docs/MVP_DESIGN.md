# MVP design

Reviewed before implementation, 2026-09-30. Independent custom node project;
no ComfyUI core modifications, outbound calls, model downloads or external editor automation.

## Boundaries

`src/local_edit_helper/core` operates on Pillow images and NumPy arrays, with SciPy morphology.
It owns crop geometry, masks, conservative RGB statistics, PNG metadata and disk jobs.
`prompt/builder.py` builds inspectable instructions from the request and optional selected context.
`bridge/manual.py` orchestrates the persisted manual handoff. No speculative API adapters.
`comfy/` alone imports ComfyUI, aiohttp or Torch: routes, storage-root selection and tensor conversion.
`web/extension/extension.js` registers an Open Editor button on one loader node. The editor also has a
direct local URL and works without a graph. Plain ES modules, Canvas 2D, no build dependencies.

## Geometry and image contracts

- Pillow RGB/RGBA, 8-bit PNG MVP. Keep source alpha and textual PNG metadata in final output.
- Masks are L images: 0 preserve, 255 edit; no alpha inversion. Mask size must equal source.
- Bounds are integer `[left, top, right, bottom]`, right/bottom exclusive.
- Use all nonzero mask pixels for bbox. Empty mask has no crop and export is rejected clearly.
- Crop factor >=1 (default 2), ceil bbox dimensions times factor; minimum size default 64.
- Round requested width/height up to `multiple_of` (default 1); optionally make square.
- Shift rectangle into image while preserving requested extent where possible, then clamp.
  If image limits prevent a multiple or square containing the complete selection, containment wins;
  return a visible warning. Never discard selected pixels to satisfy size policy.
- Output policy `native` or `limit_1024`: latter downsizes longest edge only, with aspect preserved.
  Backend returns both native bounds and exported dimensions; UI never duplicates crop math.
- Preview endpoint saves DRAFT mask/settings and returns exact clean crop. Prepare recomputes with
  the same function and freezes source/mask/crop. Editing a prepared crop requires a new job.
- Imported result policy `strict` rejects aspect mismatch >2%; smaller rounding differences are
  reported. `contain` explicitly fits proportionally into native crop, uncovered pixels transparent.
  Incoming RGBA alpha multiplies composite coverage. No automatic registration in v0.1.

## Image algorithms

Use Pillow/NumPy/SciPy library primitives rather than vendor a Torch-based crop/stitch engine.
SciPy maximum/minimum filters replace a measured slow Pillow rank-filter path (1024-square,
radius 16: approximately 0.95 seconds versus 0.007 seconds on the development machine).
Color correction samples an exterior mask ring, only where returned alpha is opaque.
Skip fewer than 64 samples. Per-channel mean/std correction with epsilon, scale clamped
to [0.8, 1.25], mean offset limited to 32/255, strength 0..1. Flat channels use mean-only
correction. Report skipped/corrected sample counts; Off and strength zero are exact no-ops.

Feathering is inward: blurred mask multiplied by original mask, so zero mask pixels stay zero.
Blend rounded uint8 RGB only inside crop; preserve source alpha. Outside original nonzero mask,
all source channel values remain bit-identical, including when feather >0.
Seam mask is dilation minus erosion of binary mask (square structuring element), width in native
pixels, clipped to image. Empty mask produces zero seam. A full mask has a border band, not full fill.
Seam refinement is a separate opt-in graph operation, allowed to modify only this band.

## Persistent state and files

Storage injected into JobStore, runtime default `output/gpt_local_edit/jobs/<UUID hex>/`.
Schema version 1 JSON: id, state, revision, created_at/updated_at, source_size, source_metadata,
crop_settings, crop bounds/native/export sizes, mask convention/bbox, prompt, processing settings,
warnings, artifact names. Atomic JSON replace. Validate schema, id, state and artifact names.
Serialize local operations; reject stale revision (409) so another tab cannot silently overwrite.
No database. Reopen by ID or recent-jobs list; corrupt jobs are reported without hiding valid jobs.

States: DRAFT -> READY_FOR_EXTERNAL_EDIT -> WAITING_FOR_RESULT -> RESULT_IMPORTED ->
COMPOSITED -> FINALIZED. Import may skip WAITING. Reimport resets derived outputs; recomposite
uses original imported pixels, never the previous correction. Finalized jobs are read-only.
Create UUID directories exclusively; never accept arbitrary filesystem paths from requests.

Export fixed artifacts: original.png, mask.png, crop.png, crop_mask.png, prompt.txt, metadata.json,
preview.png. Original source PNG text is preserved, manifest stores normalized and raw metadata.
Result/composite revisions get unique filenames so failed writes do not corrupt accepted outputs.
Optional debug outputs include normalized result, matched crop, composite mask, seam and bbox.
Finalize saves final.png with original metadata plus namespaced helper provenance; retains original
generation metadata as provenance, not a claim that it fully describes the edited image.

## UI and routes

Local base `/gpt-local-edit`. Editor GET `/editor`, assets under `/assets/`.
JSON responses `{job: manifest}` for mutations; errors `{error: message}` with 400/404/409.
All mutations require same-origin custom header `X-Local-Edit: 1`, bounded bodies and known fields.
File routes whitelist recorded artifact names. No OS shell launch route; Open Crop and downloadable
ZIP package provide portable handoff; show local job path for opening in file explorer manually.

- GET `/jobs`: `{jobs: [...], errors: [...]}`; POST multipart `/jobs` image -> DRAFT.
- GET `/jobs/{id}`; GET `/jobs/{id}/files/{name}`; GET `/jobs/{id}/download` ZIP.
- POST multipart `/jobs/{id}/preview`: mask PNG, settings JSON, revision.
- POST JSON `/jobs/{id}/prompt`: request, context -> prompt (non-mutating).
- POST JSON `/jobs/{id}/prepare`: revision, prompt -> READY.
- POST JSON `/jobs/{id}/sent`: revision -> WAITING.
- POST multipart `/jobs/{id}/import`: image, policy, revision -> RESULT_IMPORTED.
- POST JSON `/jobs/{id}/composite`: revision, color_enabled, strength, feather, seam_width,
  debug -> COMPOSITED.
- POST JSON `/jobs/{id}/finalize`: revision -> FINALIZED.

Canvas supports brush, erase, bounded undo/redo, zoom-at-pointer, middle/space-drag pan, fit.
Changes debounce preview requests; serialize saves, ignore obsolete responses, flush before Prepare.
Mask remains full resolution. Explicit active job/state, pipeline stages, previews (source, clean
crop, imported result, composite, seam), metadata disclosure, prompt edit and copy, file drop areas.
Persist drafts and reload job list on open. User-facing errors are inline; no silent distortion.

## ComfyUI finishing

One `GPTLocalEditJob` node loads persisted composite and seam MASK plus prompt from explicit job ID.
Fingerprint manifest revision to avoid stale graph cache. Node button opens editor with that ID.
Use existing VAEEncode, SetLatentNoiseMask, KSampler (suggested denoise 0.08–0.25), VAEDecode,
and ImageCompositeMasked with the seam mask to enforce preservation outside the band after VAE.
Provide example workflow with replaceable checkpoint; no checkpoint bundled or automatically fetched.

## Review and validation

Highest risks: coordinate mismatch, stale async preview, unsupported source modes, unsafe paths,
mutable exported masks, broad color statistics, VAE drift outside seam. Contracts above address each.
Tests cover geometry edges/corners, empty/full masks, metadata parsing, import policies, alpha,
flat colors, outside-mask invariance, manifest corruption, state/revision transitions and reload.
Run real ComfyUI startup with only this custom node enabled, HTTP synthetic round trip, frontend
syntax checks and browser interaction against the local editor. No ChatGPT automation is involved.
