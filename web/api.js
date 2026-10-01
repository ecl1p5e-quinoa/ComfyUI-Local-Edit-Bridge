export const BASE = location.pathname.replace(/\/editor\/?$/, "");
export async function request(path = "", data = undefined) {
    const options = { cache: "no-store" };
    if (data !== undefined) {
        options.method = "POST";
        options.headers = { "X-Local-Edit": "1" };
        if (data instanceof FormData) options.body = data;
        else {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(data);
        }
    }
    const response = await fetch(BASE + path, options);
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); }
    catch {
        if (response.status === 405) throw new Error("ComfyUI is running an older backend. Restart ComfyUI, then reload this editor (HTTP 405).");
        throw new Error("Server returned HTTP " + response.status + ": " + text.slice(0, 160));
    }
    if (!response.ok) throw new Error(result.error || "Request failed (" + response.status + ").");
    return result;
}
export function assetURL(job, key) {
    return BASE + "/jobs/" + job.id + "/files/" + job.files[key] + "?revision=" + job.revision;
}
export function loadImage(url) {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("Could not load image preview."));
        image.src = url;
    });
}
