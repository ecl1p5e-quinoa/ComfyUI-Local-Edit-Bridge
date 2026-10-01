import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function openEditor(jobId = "") {
    window.open(api.apiURL("/gpt-local-edit/editor") + (jobId ? "?job=" + encodeURIComponent(jobId) : ""), "_blank", "noopener");
}
app.registerExtension({
    name: "local-edit-helper.manual",
    commands: [{ id: "local-edit-helper.open", label: "Open Local Edit Bridge", function: () => openEditor() }],
    menuCommands: [{ path: ["Tools"], commands: ["local-edit-helper.open"] }],
    nodeCreated(node) {
        if (node.comfyClass !== "GPTLocalEditJob") return;
        node.addWidget("button", "Open Editor", null, () => {
            openEditor(node.widgets?.find(widget => widget.name === "job_id")?.value || "");
        }, { serialize: false });
    }
});
