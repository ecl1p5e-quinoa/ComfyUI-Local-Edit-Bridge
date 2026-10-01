import { BASE, request, assetURL, loadImage } from "./api.js";
import { MaskCanvas } from "./canvas.js";

const $ = id => document.getElementById(id);
let job = null, directory = "", busy = false, dirty = 0, saved = 0, timer = null, pending = null;
let importFile = null;
const painter = new MaskCanvas($("canvas"), markDirty, value => { $("zoom").textContent = value + "%"; });

function message(text, kind = "") {
    $("message").textContent = text;
    $("message").className = kind;
}
function showImage(id, key) {
    const element = $(id);
    element.hidden = !job?.files[key];
    if (!element.hidden) element.src = assetURL(job, key);
    else element.removeAttribute("src");
}
function link(id, url) {
    $(id).hidden = !url;
    if (url) $(id).href = url;
    else $(id).removeAttribute("href");
}
function controls() {
    const draft = job?.state === "DRAFT";
    for (const element of document.querySelectorAll("button, input, select, textarea")) element.disabled = busy;
    for (const id of ["brush", "eraser", "clear", "brush-size", "undo", "redo", "crop-factor", "min-size", "multiple", "square", "output-policy", "request", "context", "generate", "prompt"]) {
        $(id).disabled = busy || !draft;
    }
    $("prepare").disabled = busy || !draft || !job?.crop || !$("prompt").value.trim();
    $("prompt").disabled = busy || !job;
    $("prompt").readOnly = !draft;
    $("sent").disabled = busy || job?.state !== "READY_FOR_EXTERNAL_EDIT";
    const canImport = job && ["READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT", "RESULT_IMPORTED", "COMPOSITED"].includes(job.state);
    $("result-file").disabled = $("import-policy").disabled = busy || !canImport;
    $("retry-import").disabled = busy || !canImport || !importFile;
    const canComposite = job && ["RESULT_IMPORTED", "COMPOSITED"].includes(job.state);
    for (const id of ["composite", "color-enabled", "strength", "mask-expansion", "feather", "seam-width", "debug"]) $(id).disabled = busy || !canComposite;
    $("finalize").disabled = busy || job?.state !== "COMPOSITED";
    for (const id of ["copy-id", "copy-folder", "copy-prompt", "fit"]) $(id).disabled = busy || !job;
    for (const button of document.querySelectorAll("[data-rework]")) {
        const step = button.dataset.rework;
        button.disabled = busy || !job || (step === "import" && draft)
            || (step === "blend" && !job?.files.aligned) || (step === "final" && !job?.files.composite);
    }
    for (const button of document.querySelectorAll("[data-restore]")) {
        button.disabled = busy || !job?.rework_backup || job.rework_step !== button.dataset.restore;
        button.textContent = (job?.rework_undone ? "Redo " : "Undo ") + (button.dataset.restore === "final" ? "save rework" : "rework");
    }
    for (const id of ["compare-position", "compare-mode"]) $(id).disabled = busy || !job?.files.composite;
    painter.editable = !!draft && !busy;
    painter.updateCursor();
    document.body.classList.toggle("busy", busy);
}
function render() {
    if (!job) { controls(); return; }
    $("state").textContent = job.state.replaceAll("_", " ");
    $("job-id").textContent = job.id;
    $("dimensions").textContent = job.source_size.join(" × ") + " source pixels";
    $("directory").textContent = directory;
    $("metadata").textContent = JSON.stringify(job.source_metadata.normalized, null, 2);
    $("raw-metadata").textContent = JSON.stringify(job.source_metadata.raw, null, 2);
    $("empty").hidden = true;
    painter.bounds = job.crop?.bounds || null;
    painter.render();
    $("crop-info").textContent = job.crop
        ? "Bounds [" + job.crop.bounds.join(", ") + "] · export " + job.crop.export_size.join(" × ") + " px"
        : "Paint a mask to calculate the crop.";
    for (const [id, key] of [["crop-preview", "crop"], ["overlay-preview", "preview"], ["import-preview", job.handoff === "original_overlay" ? "returned" : "aligned"], ["before-preview", "original"], ["after-preview", "composite"], ["seam-preview", "seam"]]) showImage(id, key);
    $("crop-empty").hidden = !!job.files.crop;
    const prepared = job.state !== "DRAFT";
    const fullImage = job.handoff === "original_overlay";
    link("open-crop", prepared ? assetURL(job, fullImage ? "original" : "crop") : "");
    $("open-crop").textContent = fullImage ? "Download image 1 · Original" : "Download image 1 · Clean crop";
    $("open-crop").download = fullImage ? "01-original.png" : "crop.png";
    link("open-overlay", prepared && ["original_overlay", "crop_overlay"].includes(job.handoff) && job.files.preview ? assetURL(job, "preview") : "");
    $("handoff-help").textContent = prepared && job.handoff !== "crop_overlay"
        ? "This job uses a previous handoff. Rework step 3, rebuild the prompt and Prepare to export two matching crops."
        : "Prepare opens a folder with the clean crop, overlay guide and prompt. Select all three files and drag them into your GPT conversation, then import the edited crop in step 4.";
    $("import-policy").querySelector('option[value="contain"]').textContent = fullImage ? "Fit inside original · transparent padding" : "Fit inside crop · transparent padding";
    $("open-handoff").hidden = !prepared || job.handoff !== "crop_overlay";
    link("save-final", job.files.final ? assetURL(job, "final") : "");
    $("processing-info").textContent = job.files.composite
        ? "Applied: " + (job.processing.color_enabled ? "color match " + job.processing.strength : "color match off")
          + ", mask expansion " + (job.processing.mask_expansion ?? 0) + " px, inward feather " + job.processing.feather + " px, seam " + job.processing.seam_width + " px. "
          + (job.processing.expansion_clipped ? "Expansion reached the crop boundary; enlarge the crop in step 2 for more room. " : "")
          + (job.processing.color_report?.applied
              ? "Correction measured from " + job.processing.color_report.samples + " surrounding pixels."
              : job.processing.color_enabled ? "Color correction skipped: not enough opaque context pixels." : "")
        : "Color match samples unchanged surroundings. Expansion grows the blend area; feathering softens its inner edge.";
    const stage = job.state === "DRAFT" ? (job.crop ? 2 : 0)
        : ["READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT"].includes(job.state) ? 3 : 4;
    const steps = ["mask", "crop", "prompt", "import", "blend"];
    for (const [index, name] of steps.entries()) {
        const section = document.querySelector('[data-step="' + name + '"]');
        const ready = index <= stage || name === "crop";
        section.classList.toggle("current", index === stage);
        section.classList.toggle("locked", !ready);
        section.classList.toggle("ready", ready);
        section.querySelector(".step-status").textContent = job.state === "FINALIZED" ? "Complete"
            : index < stage ? "Ready" : index === stage ? "Next" : ready ? "Adjust crop" : "Complete previous step";
    }
    $("compare-empty").hidden = !!job.files.composite;
    $("compare-divider").hidden = !job.files.composite;
    updateComparison();
    [...$("pipeline").children].forEach((element, index) => element.classList.toggle("active", index <= stage));
    controls();
}
function setJob(response) {
    job = response.job;
    directory = response.directory || directory;
}
function cropSettings() {
    return { crop_factor: Number($("crop-factor").value), min_size: Number($("min-size").value),
        multiple_of: Number($("multiple").value), square: $("square").checked, output_policy: $("output-policy").value };
}
function markDirty() {
    if (!job || job.state !== "DRAFT") return;
    dirty += 1;
    $("factor-value").textContent = Number($("crop-factor").value).toFixed(1) + "×";
    clearTimeout(timer);
    timer = setTimeout(() => flushPreview().catch(error => message(error.message, "error")), 220);
}
async function flushPreview() {
    clearTimeout(timer);
    if (pending) { await pending; if (dirty > saved) return flushPreview(); return; }
    pending = (async () => {
        while (job?.state === "DRAFT" && dirty > saved) {
            const generation = dirty, id = job.id, settings = cropSettings(), blob = await painter.blob();
            const form = new FormData();
            form.set("mask", blob, "mask.png");
            form.set("settings", JSON.stringify(settings));
            form.set("revision", String(job.revision));
            const result = await request("/jobs/" + id + "/preview", form);
            if (job.id !== id) return;
            setJob(result);
            saved = generation;
            if (dirty === generation) {
                render();
                message(job.warnings.length ? job.warnings.join(" ") : "Draft saved. Both GPT images use the exact crop shown here.", job.warnings.length ? "" : "success");
            }
        }
    })();
    try { await pending; } finally { pending = null; }
}
async function action(operation) {
    if (busy) { message("An operation is still running. Please wait for it to finish."); return; }
    busy = true; painter.end(); controls();
    try { await operation(); }
    catch (error) { message(error.message, "error"); $("message").scrollIntoView({ block: "nearest" }); }
    finally { busy = false; controls(); }
}
async function recent() {
    const result = await request("/jobs");
    $("jobs").replaceChildren(new Option("Choose a saved job…", ""));
    for (const item of result.jobs) {
        $("jobs").add(new Option(item.updated_at.slice(0, 16).replace("T", " ") + " · " + item.state + " · " + item.id.slice(0, 8), item.id));
    }
    $("jobs").value = job?.id || "";
    if (result.errors.length) message(result.errors.length + " unreadable job(s): " + result.errors.map(item => item.id.slice(0, 8) + ": " + item.error).join("; "), "error");
}
async function openJob(response) {
    setJob(response); dirty = saved = 0;
    importFile = null; $("retry-import").hidden = true;
    $("import-status").textContent = "Choose or drop a saved image file. If its proportions changed, use the Fit inside option.";
    $("import-status").className = "muted";
    const [source, mask] = await Promise.all([loadImage(assetURL(job, "original")), loadImage(assetURL(job, "mask"))]);
    painter.setImage(source, mask);
    const settings = { crop_factor: 2, min_size: 64, multiple_of: 1, square: false, output_policy: "native", ...job.crop_settings };
    $("crop-factor").value = settings.crop_factor; $("factor-value").textContent = settings.crop_factor.toFixed(1) + "×";
    $("min-size").value = settings.min_size; $("multiple").value = String(settings.multiple_of);
    $("square").checked = settings.square; $("output-policy").value = settings.output_policy;
    $("prompt").value = job.prompt; $("request").value = job.prompt_inputs?.request || ""; $("context").value = job.prompt_inputs?.context || "";
    $("import-policy").value = job.import?.policy || "contain";
    $("color-enabled").checked = job.processing.color_enabled ?? true;
    $("strength").value = job.processing.strength ?? 1;
    $("strength-value").textContent = Number($("strength").value).toFixed(2);
    $("mask-expansion").value = job.processing.mask_expansion ?? 0;
    $("feather").value = job.processing.feather ?? 8; $("seam-width").value = job.processing.seam_width ?? 8;
    $("debug").checked = job.processing.debug || false;
    history.replaceState(null, "", "?job=" + job.id);
    localStorage.setItem("gpt-local-edit:last-job", job.id);
    render();
    message(job.warnings.length ? job.warnings.join(" ") : "Job loaded from disk. " + (job.state === "DRAFT" ? "Paint your edit region." : "Use Rework this step to revise a completed step."));
    await recent();
}
async function uploadSource(file) {
    if (!file) return;
    await flushPreview();
    const form = new FormData(); form.set("image", file, file.name);
    await openJob(await request("/jobs", form));
}
async function importResult(file) {
    if (!file) throw new Error("Drop a saved image file from your computer.");
    if (!job) throw new Error("Load a source image and prepare the handoff first.");
    importFile = file; $("retry-import").hidden = false;
    $("import-status").textContent = "Importing " + file.name + "…";
    $("import-status").className = "muted";
    try {
        if (!["READY_FOR_EXTERNAL_EDIT", "WAITING_FOR_RESULT", "RESULT_IMPORTED", "COMPOSITED"].includes(job.state)) {
            throw new Error("Prepare a job before importing; finalized jobs are read-only.");
        }
        const form = new FormData(); form.set("image", file, file.name);
        form.set("revision", String(job.revision)); form.set("policy", $("import-policy").value);
        setJob(await request("/jobs/" + job.id + "/import", form));
        render(); await recent();
        const status = job.warnings.length ? job.warnings.join(" ") : "Result imported. Review the fitted image, then composite.";
        $("import-status").textContent = file.name + ": " + status;
        $("import-status").className = "success";
        message(status, "success");
    } catch (error) {
        $("import-status").textContent = file.name + ": " + error.message
            + (error.message.includes("aspect ratio") ? " Select Fit inside original/crop, then click Retry selected image." : "");
        $("import-status").className = "error";
        message(error.message, "error");
    }
}
async function copy(text) {
    try { await navigator.clipboard.writeText(text); message("Copied to clipboard.", "success"); }
    catch { message("Clipboard unavailable. Select and copy the visible text manually.", "error"); }
}
function drop(target, callback) {
    target.addEventListener("dragover", event => { event.preventDefault(); target.classList.add("drag-over"); });
    target.addEventListener("dragleave", () => target.classList.remove("drag-over"));
    target.addEventListener("drop", event => {
        event.preventDefault(); target.classList.remove("drag-over");
        if (event.dataTransfer.files.length) action(() => callback(event.dataTransfer.files[0]));
        else {
            message("Save the image to your computer first, then drop the saved file here.", "error");
            if (target.id === "result-drop") { $("import-status").textContent = $("message").textContent; $("import-status").className = "error"; }
        }
    });
}
$("source-file").onchange = event => { const file = event.target.files[0]; event.target.value = ""; action(() => uploadSource(file)); };
$("result-file").onchange = event => { const file = event.target.files[0]; event.target.value = ""; action(() => importResult(file)); };
$("retry-import").onclick = () => action(() => importResult(importFile));
drop($("canvas-drop"), uploadSource); drop($("result-drop"), importResult);
$("refresh").onclick = () => action(async () => { await flushPreview(); await recent(); });
$("jobs").onchange = event => { const id = event.target.value; if (id) action(async () => { await flushPreview(); await openJob(await request("/jobs/" + id)); }); };
$("brush").onclick = () => { painter.tool = "brush"; $("brush").classList.add("selected"); $("eraser").classList.remove("selected"); };
$("eraser").onclick = () => { painter.tool = "eraser"; $("eraser").classList.add("selected"); $("brush").classList.remove("selected"); };
$("brush-size").oninput = () => { painter.brushSize = Number($("brush-size").value); $("brush-value").textContent = painter.brushSize + " px"; painter.render(); };
$("clear").onclick = () => painter.clear(); $("undo").onclick = () => painter.undo(); $("redo").onclick = () => painter.redo();
$("fit").onclick = () => painter.fit();
for (const id of ["crop-factor", "min-size", "multiple", "square", "output-policy"]) $(id).addEventListener("input", markDirty);
$("strength").oninput = () => { $("strength-value").textContent = Number($("strength").value).toFixed(2); };
$("generate").onclick = () => action(async () => {
    const result = await request("/jobs/" + job.id + "/prompt", { request: $("request").value, context: $("context").value });
    $("prompt").value = result.prompt;
    message("Prompt ready. Review or edit it before preparing the job.", "success");
});
$("prepare").onclick = () => action(async () => {
    await flushPreview();
    setJob(await request("/jobs/" + job.id + "/prepare", { revision: job.revision, prompt: $("prompt").value }));
    render(); await recent();
    await openHandoff();
    message("GPT folder opened. Select all three files and drag them into your GPT conversation; return the edited image in step 4.", "success");
});
$("sent").onclick = () => action(async () => {
    setJob(await request("/jobs/" + job.id + "/sent", { revision: job.revision }));
    render(); await recent(); message("Waiting for your manually saved result.", "success");
});
$("copy-prompt").onclick = () => copy($("prompt").value);
$("copy-id").onclick = () => copy(job.id);
$("copy-folder").onclick = () => copy(directory);
$("composite").onclick = () => action(async () => {
    setJob(await request("/jobs/" + job.id + "/composite", { revision: job.revision, color_enabled: $("color-enabled").checked,
        strength: Number($("strength").value), feather: Number($("feather").value),
        mask_expansion: Number($("mask-expansion").value), seam_width: Number($("seam-width").value), debug: $("debug").checked }));
    render(); await recent(); message("Composite saved. Compare before/after and inspect the seam mask below.", "success");
});
$("finalize").onclick = () => action(async () => {
    setJob(await request("/jobs/" + job.id + "/finalize", { revision: job.revision }));
    render(); await recent(); message("Final PNG saved in the job folder. Use Save final PNG to download it.", "success");
});
for (const section of document.querySelectorAll("[data-step]")) {
    const toolbar = document.createElement("div");
    toolbar.className = "step-history";
    const rework = document.createElement("button"), restore = document.createElement("button");
    rework.dataset.rework = restore.dataset.restore = section.dataset.step;
    rework.textContent = "↶ Rework this step";
    rework.title = section.dataset.step === "prompt"
        ? "Edit the existing prompt again. Keep your text, mask and crop; clear dependent results."
        : "Keep this step’s content and settings, reopen editing, and clear dependent results.";
    restore.textContent = "Undo rework";
    restore.title = "Restore the most recent rework in this server session. Restarting ComfyUI clears this temporary checkpoint.";
    toolbar.append(rework, restore);
    const heading = section.querySelector(".step-heading");
    const status = document.createElement("span");
    status.className = "step-status";
    status.textContent = "Load an image";
    heading.querySelector("h2").append(status);
    heading.append(toolbar);
}
for (const button of document.querySelectorAll("[data-rework], [data-restore]")) {
    button.onclick = () => action(async () => {
        await flushPreview();
        const step = button.dataset.rework;
        const settings = Object.fromEntries(["color-enabled", "strength", "mask-expansion", "feather", "seam-width", "debug", "import-policy"].map(id => [id, $(id).type === "checkbox" ? $(id).checked : $(id).value]));
        const response = await request("/jobs/" + job.id + (step ? "/rework" : "/undo-rework"),
            { revision: job.revision, prompt: $("prompt").value, prompt_inputs: { request: $("request").value, context: $("context").value }, ...(step ? { step } : {}) });
        await openJob(response);
        if (step) {
            for (const [id, value] of Object.entries(settings)) {
                if ($(id).type === "checkbox") $(id).checked = value;
                else $(id).value = value;
            }
            $("strength-value").textContent = Number($("strength").value).toFixed(2);
        }
        message(step ? "Editing reopened. Your content and settings are preserved; dependent results have been cleared."
            : "Saved step state restored.", "success");
    });
}
async function openHandoff() {
    const result = await request("/jobs/" + job.id + "/open-handoff", { revision: job.revision });
    message("Folder opened: " + result.directory + ". Select all three files and drag them into GPT.", "success");
}
$("open-handoff").onclick = () => action(openHandoff);
$("prompt").addEventListener("input", controls);

function updateComparison(value = Number($("compare-position").value)) {
    value = Math.min(100, Math.max(0, value));
    $("compare-position").value = String(value);
    $("after-preview").style.clipPath = "inset(0 0 0 " + value + "%)";
    $("compare-divider").style.left = value + "%";
    $("compare-divider").hidden = !job?.files.composite || $("compare-mode").value === "click";
}
function moveComparison(event) {
    if (!job?.files.composite || $("compare-mode").value !== "slide") return;
    const rect = $("compare-frame").getBoundingClientRect();
    updateComparison((event.clientX - rect.left) / rect.width * 100);
}
$("compare-frame").addEventListener("pointermove", moveComparison);
$("compare-frame").addEventListener("pointerdown", event => {
    if (!job?.files.composite) return;
    $("compare-frame").setPointerCapture(event.pointerId);
    if ($("compare-mode").value === "click") updateComparison(100);
    else moveComparison(event);
});
for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
    $("compare-frame").addEventListener(type, () => {
        if ($("compare-mode").value === "click") updateComparison(0);
    });
}
$("compare-position").oninput = () => updateComparison();
$("compare-mode").onchange = () => {
    const slide = $("compare-mode").value === "slide";
    $("compare-position").hidden = !slide;
    updateComparison(slide ? 50 : 0);
};
window.addEventListener("beforeunload", event => {
    if (pending || dirty > saved) { event.preventDefault(); event.returnValue = ""; }
});
controls();
action(async () => {
    await recent();
    const id = new URLSearchParams(location.search).get("job") || localStorage.getItem("gpt-local-edit:last-job");
    if (id) await openJob(await request("/jobs/" + encodeURIComponent(id)));
});
