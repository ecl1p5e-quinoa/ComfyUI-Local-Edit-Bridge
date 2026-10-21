# Local Edit Bridge for ComfyUI

English | [简体中文](README.zh-CN.md)

Paint over the part of an image you want to change, send that crop to an image-editing model, then bring the result back into ComfyUI. Local Edit Bridge handles the crop, the location guide, and blending the edited area back into your original image.

This is an early project, close to an MVP. The basic editing loop works, but there are still rough edges. It is meant for one person working locally on one edit at a time.

The plugin does not call an image API, upload files, control your browser, or download models. You send the files yourself and save the result yourself. No API key is needed for the plugin; access to your chosen image service is separate.

## What you can do

- Paint and erase a mask, undo strokes, zoom in, and pan around the image.
- See the exact crop you will send, including the surrounding area that helps the model understand the edit.
- Prepare two matching images and an editable prompt in one folder.
- Reopen a step without losing the mask or prompt you already worked on.
- Adjust color matching, expand the blend area, and soften its edges.
- Compare the original and edited image with a sliding divider or by holding down the pointer.
- Reopen saved jobs and use the result in a normal ComfyUI workflow.

![Editor preview](docs/editor-roundtrip.png)

## Install

You need a working ComfyUI installation with Python 3.10 or newer. The plugin uses Pillow, NumPy, and SciPy. Run the commands below with the Python that runs ComfyUI, so the packages end up in the right place.

If you already installed this project under its old name, `comfyui-gpt-local-edit-helper`, update that copy. Do not install a second copy alongside it.

### Windows portable ComfyUI

Open PowerShell in your portable folder, the one containing both `ComfyUI` and `python_embeded`. Then run:

```powershell
git clone https://github.com/ecl1p5e-quinoa/ComfyUI-Local-Edit-Bridge.git .\ComfyUI\custom_nodes\ComfyUI-Local-Edit-Bridge
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI-Local-Edit-Bridge\requirements.txt
```

Restart ComfyUI after installation. Refreshing the browser alone does not load a new plugin.

### Other Python-based ComfyUI installations

Open a terminal in the `ComfyUI` folder and activate the Python environment you normally use to start ComfyUI. Then run:

```sh
git clone https://github.com/ecl1p5e-quinoa/ComfyUI-Local-Edit-Bridge.git custom_nodes/ComfyUI-Local-Edit-Bridge
python -m pip install -r custom_nodes/ComfyUI-Local-Edit-Bridge/requirements.txt
```

Restart ComfyUI when the commands finish.

If you do not have Git, use **Code → Download ZIP** on this repository's GitHub page. Extract the plugin into `ComfyUI/custom_nodes/ComfyUI-Local-Edit-Bridge`. That folder should directly contain `__init__.py`, `requirements.txt`, and `web`, without another repository folder nested inside it. Then run the dependency command for your installation above.

### Open the editor

With ComfyUI running, use any of these:

- Open **Tools → Open Local Edit Bridge**.
- Search for the **Local Edit Bridge** node, add it, and click **Open Editor**. Its category is `image/local edit`.
- Open [the editor directly](http://127.0.0.1:8188/gpt-local-edit/editor). If your ComfyUI uses another port, replace `8188` with that port.

You do not need to build or run a node graph to use the editor. The node is useful when you want to continue editing the result in ComfyUI.

To update later, run `git pull` inside the installed plugin folder, then restart ComfyUI and refresh the editor.

## Your first edit

The first two cards sit side by side on a wide screen. Follow the step numbers, then check the large before/after view at the bottom.

### Step 1: Load an image and paint the area

Click **Load image**, or drop a saved image file onto **Original & edit**. PNG is a good choice if you want to keep the generation information stored in the image.

Use **Brush** to paint the part you want changed and **Eraser** to remove paint. The colored overlay shows your selection. In the saved mask, white means edit and black means keep.

- Change **Brush size** to adjust the brush. The circle under the pointer shows its size.
- Use **Undo** and **Redo**, or Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z. Ctrl+Y also works for redo. These shortcuts apply when the canvas is hovered or focused; text boxes keep their usual shortcuts.
- Scroll to zoom. Hold Space and drag, or drag with the middle mouse button, to move around. **Fit view** fits the image back into the canvas.

**Image metadata** shows generation information the plugin can read, including common ComfyUI and A1111/Forge PNG data. It may not understand every custom workflow, so the original PNG text is also available.

### Step 2: Check the crop

**Exact GPT crop** shows the clean image that will go to the model. Both exported images use this crop, not the full original image.

| Setting | What it does |
| --- | --- |
| Crop factor | Includes more or less of the area around your painted selection. The default is 2. |
| Minimum px | Sets the minimum crop size, where the source image has room. |
| Multiple of | Tries to make the width and height multiples of the selected number. Leave it at 1 if you do not need this. |
| Square crop | Tries to make the crop square. |
| Output size | Keeps the crop's original pixel size, or shrinks its longest side to at most 1024 pixels. |

The crop stays inside the source image and keeps the painted area covered. At the image edges, a square shape or exact size multiple may not be possible.

### Step 3: Prepare the files and send them

1. In **Your edit request**, describe what you want changed.
2. If useful, expand **Optional selected generation context** and add details about the character or original generation. The plugin does not automatically put all your image metadata into the prompt.
3. Click **Build editing prompt**. Read the text in **Final prompt** and change anything you want.
4. Click **Prepare for GPT & open folder**. This saves the prepared edit and opens a folder containing just these three files:

| File | Purpose |
| --- | --- |
| `01-crop.png` | The clean crop the model should edit. |
| `02-overlay.png` | The same crop with a colored, partly transparent mark showing where to edit. |
| `prompt.txt` | Your editing instructions. |

Select all three files and drag them into your image-editing conversation. If the service does not accept text files, attach the two images and paste the contents of `prompt.txt` into the message. Ask for an edited version of the clean crop; the colored guide should not appear in the result.

**More options** contains **Copy prompt**, both image downloads, **Open GPT folder**, and **Mark as sent**. Marking the job as sent is optional; you can import a result without it.

Preparing the files locks the earlier editing controls until you choose **Rework this step**. Save your prompt by preparing the job before you refresh the page; unfinished prompt changes can be lost.

### Step 4: Bring the edited image back

Save the image returned by the model to your computer. Drop that saved file onto **Returned edit**, or click **Import GPT result** and select it. Dragging an image directly from a chat page may only pass a link, which the editor cannot import.

Leave **Import fitting** at **Fit inside crop** to keep the returned image's proportions. Any unused space is left transparent. **Check aspect ratio (strict)** accepts only a small difference in width-to-height ratio, up to 2%. If it rejects your image, choose **Fit inside crop** and click **Retry selected image**.

The plugin resizes the result to fit the crop. It does not automatically move or rotate the contents to line them up with the original.

### Step 5: Blend, compare, and save

Start with the defaults, then click **Composite & preview seam** to see the result.

| Setting | What it does |
| --- | --- |
| Color match | Uses the surrounding area to help the returned crop match the original's colors. On by default. |
| Strength | Controls the amount of color correction. The default is 1, the full correction. |
| Mask expansion px | Grows the area used for blending by 0–128 original-image pixels. The default is 0. |
| Inward feather px | Softens the edge toward the inside of the blend area. |
| Seam width px | Sets how far the optional seam mask extends on each side of the edge. This mask is for later touch-ups. |

Mask expansion changes the final blend area, not your painted mask or the images sent to the model. It stops at the crop boundary. If you need more room, enlarge the crop in Step 2 and prepare a new edit. Repeated previews always start from the original mask, so expansion does not keep adding up.

Use **Before / after** at the bottom to inspect the result. **Slide** lets you move the dividing line; **Hold for Before** shows the original while you hold the pointer down and the result when you release it.

When it looks right, click **Finalize PNG** to write `final.png` into the job folder. **Save final PNG** downloads a copy through your browser. The saved image keeps the original dimensions and transparency. Pixels outside the final blend mask stay unchanged.

## Change an earlier step

Click **Rework this step** beside that step's title. It makes the step editable again and clears later results that depend on it. It keeps your inputs: repainting does not erase your prompt, and rewriting the prompt does not erase your mask.

**Undo rework** brings back the state before the latest rework; **Redo rework** switches back again. Only one such checkpoint is kept across the editor. It survives a page refresh while the same ComfyUI process is running, but a new rework replaces it and restarting ComfyUI clears it.

Brush undo is separate. It has a memory limit and lasts only while that image stays open.

## Where your files go

Choose a saved job from **Active job** to continue it. Loading a new source image creates a new job.

By default, jobs are stored under:

```text
ComfyUI/output/gpt_local_edit/jobs/<job-id>/
```

If you changed ComfyUI's output folder, jobs go there instead. In Step 3, expand **Local job folder** to see and copy the exact path.

The folder holds the original image, mask, crop, prompt, returned image, current blend, and saved result. `metadata.json` records the settings. The `gpt-handoff` subfolder contains the three files you send to the model.

Only the latest files for each part of the job are kept, rather than a history of every attempt. Rework undo uses a temporary copy outside the job folder. The plugin also cleans up its old replaced files when reopening an older job; it leaves unrelated files and other jobs alone. Avoid editing the same job in two tabs: if one tab saves a newer version, the other will need to reload it.

Original PNG text and color-profile data are kept, and the final PNG adds a record of this edit. The original generation prompt remains a record of how the source was made; it may no longer describe the edited image exactly.

## Why use this instead of normal inpainting?

If you have used SDXL or Anima inpainting, the overall process should feel familiar: select an area, crop it with some surroundings, generate a replacement, then blend it back. You can think of the external image model as taking over the generation step normally handled by KSampler. That is a comparison of their roles, not a claim that their settings or inner workings are the same.

The interface uses GPT as its example, but any service that accepts images and text and returns an edited image can fit this process. In my experience, other models may give much worse results than gpt-image-2.

The comments below come from my own use. I find GPT much better at most image-editing tasks and understanding prompts than SDXL / Anima. Still, when you have the model and settings that made the original, traditional inpainting often does a better job of keeping the style and character consistent.

### Noise in the edited area

GPT-image can add noise even though the prompt asks it not to. My workaround is another pass over the noisy area with traditional SDXL inpainting at a very low denoise strength.

### Jagged edges after resizing

Resizing in this process can leave jagged edges. In my experience, running the image through VAE encoding and decoding once, without another edit, can help smooth them.

### Complex characters can lose their features

When fixing anatomy on a complex character, such as an anthro furry character or one made with a character LoRA, GPT may change identifying features as well. Describing those features more clearly in the prompt is worth trying, but I have found the benefit limited.

### The colored guide is only a guide

The overlay helps the model understand where to edit. It is not a strict mask passed to an image-editing API, so the model may change things outside the marked area too. If those changes cause an awkward join when you paste the crop back, try increasing **Mask expansion px** in Step 5 to include more of the nearby changes.

## Optional: touch up the seam in ComfyUI

Once you have blended the result, use **Copy ID** in the editor and paste it into the `job_id` field of the **Local Edit Bridge** node. The node gives you the blended image, a narrow mask around the join, the prompt, and the job details.

You can load [the example workflow](examples/seam_refinement.json) into ComfyUI and choose your own compatible checkpoint. It uses VAEEncode, SetLatentNoiseMask, KSampler, VAEDecode, and ImageCompositeMasked. No model is downloaded for you.

Try a denoise strength around **0.08–0.25** and adjust for your image. Keep the final **ImageCompositeMasked** node: VAE encoding and decoding can change pixels outside the sampled area, and that node puts the untouched surroundings back. If your VAE cannot handle the image's exact dimensions, add padding first, then crop the decoded image back before the final blend.

This step runs in ComfyUI. There is no one-click sampling button in the editor yet.

## Common problems and current limits

| Problem | What to try |
| --- | --- |
| The node or menu entry is missing | Check the plugin's folder, restart ComfyUI, and refresh the browser. Look at the ComfyUI terminal for missing-package errors. |
| An action returns 405 after an update | Restart ComfyUI so it loads the updated plugin, then refresh the editor. |
| Dropping a returned image does nothing | Save the image as a local file first. Check the message in Step 4, then retry or use the file picker. |
| The prepared folder does not open | Use the editor on the same computer as ComfyUI, through its local address. You can copy the path under **Local job folder**, or download the two images and copy the prompt from **More options**. |
| The mask or prompt cannot be edited | Choose **Rework this step** on that card. |
| Color match seems to do nothing | It needs enough unchanged, nontransparent surrounding pixels. It skips correction when there are too few. |
| An old job expects a full image instead of a crop | Rework Step 3, rebuild the prompt, and prepare again to use the current two-crop format. |

Uploads are limited to 32 MiB and 24 million pixels, and images must be 8-bit. This is a local, single-user tool without account-based access control.

Automatic position alignment, several result candidates per job, brush history saved across sessions, moving jobs between computers, and pasting images from the system clipboard are not implemented. Better alignment, candidate comparison, and easier seam touch-ups are possible next steps, not current features.

<details>
<summary>More detail about blending</summary>

Color matching reads a ring just outside the mask and compares channel averages and variation, skipping transparent returned pixels. It needs at least 64 usable pixels. The scale correction stays between 0.8 and 1.25, and the average shift is limited to 32/255. For a flat-color channel, only the average is adjusted. Each preview starts from the imported image, so corrections do not pile up.

The color calculation uses the stored RGB values directly. Keeping the image's color profile does not mean the plugin converts it to linear light before blending.

Feathering stays inside the mask and also respects transparency in the returned image. The seam mask is a narrow strip on both sides of the edge, made by subtracting a smaller mask from a larger one.

Crop bounds use whole pixels. The right and bottom coordinates mark where the crop stops; those pixels are not included.

</details>

## Development

The Python image-processing code is separate from ComfyUI and Torch. `prompt` builds the editing instructions, `bridge/manual.py` handles the editing steps, `comfy` connects them to ComfyUI, and `web` contains the browser editor.

For local development, open a terminal in the plugin folder. With a regular Python installation:

```sh
python -m venv .venv
```

Activate that environment using `.venv\Scripts\Activate.ps1` in PowerShell, or `source .venv/bin/activate` on Linux/macOS, then run:

```sh
python -m pip install -e ".[dev]"
python -m pytest --confcutdir=tests tests
```

This environment is only for development. You do not need to activate it to use the plugin, and it does not need a separate Torch installation.

<details>
<summary>If portable Python does not include venv</summary>

The portable Python 3.13.9 used for this project needed `virtualenv` instead. From the plugin folder under `ComfyUI/custom_nodes`, run these commands in PowerShell:

```powershell
..\..\..\python_embeded\python.exe -m pip install --target .devtools virtualenv
..\..\..\python_embeded\python.exe -c "import sys; sys.path.insert(0, '.devtools'); import virtualenv; virtualenv.cli_run(['.venv'])"
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests tests
```

</details>

`tools/make_fixture.py` creates sample images for tests. `tools/browser_smoke.cjs` checks the editor with Playwright and installed Edge, without opening ChatGPT. Set `NODE_PATH` to the folder containing the Playwright package and pass the local server URL and development Python executable. Previous test results are in the [validation notes](docs/VALIDATION.md).

## Credits and license

Cropping, blending, and color matching are existing techniques. This project puts them into an editor for sending an image to an external model and bringing the result back.

References include [InpaintCanvas](https://github.com/DenRakEiw/ComfyUI-InpaintCanvas), [CropStitch-NB2](https://github.com/amortegui84/comfyui-inpaint-cropstitch-nb2), [NKD Basic Tools](https://github.com/Nekodificador/ComfyUI-NKD-Basic-Tools), and [CropAndStitch](https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch). The before/after controls were inspired by [rgthree Image Comparer](https://github.com/rgthree/rgthree-comfy).

No code from those projects is copied or bundled here. This project's original code uses the [MIT license](LICENSE); the referenced projects keep their own licenses. See the [source review](docs/PRIOR_ART.md), [design notes](docs/MVP_DESIGN.md), and [third-party notice](THIRD_PARTY.md) for more detail.
