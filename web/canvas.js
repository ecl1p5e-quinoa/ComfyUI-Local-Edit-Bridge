export class MaskCanvas {
    constructor(canvas, onChange, onView) {
        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");
        this.mask = document.createElement("canvas");
        this.paint = this.mask.getContext("2d", { willReadFrequently: true });
        this.tint = document.createElement("canvas");
        this.image = null;
        this.bounds = null;
        this.editable = true;
        this.tool = "brush";
        this.brushSize = 32;
        this.scale = 1;
        this.offset = { x: 0, y: 0 };
        this.history = [];
        this.future = [];
        this.space = false;
        this.drag = null;
        this.hovered = false;
        this.pointer = null;
        this.onChange = onChange;
        this.onView = onView;
        canvas.tabIndex = 0;
        this.stage = canvas.parentElement;
        this.cursor = document.createElement("div");
        this.cursor.style.position = "absolute";
        this.cursor.style.display = "none";
        this.cursor.style.pointerEvents = "none";
        this.cursor.style.borderRadius = "50%";
        this.cursor.style.boxShadow = "0 0 0 1px #000, 0 0 0 2px #fff";
        this.stage.append(this.cursor);
        new ResizeObserver(() => { this.end(); this.fit(); }).observe(canvas);
        canvas.addEventListener("pointerenter", event => { this.pointer = this.point(event); this.hovered = true; this.updateCursor(); });
        canvas.addEventListener("pointerleave", () => { this.hovered = false; this.pointer = null; this.updateCursor(); });
        canvas.addEventListener("pointerdown", event => { canvas.focus({ preventScroll: true }); this.start(event); });
        canvas.addEventListener("pointermove", event => {
            this.pointer = this.point(event);
            const rect = canvas.getBoundingClientRect();
            this.hovered = this.pointer.x >= 0 && this.pointer.y >= 0 && this.pointer.x < rect.width && this.pointer.y < rect.height;
            this.move(event); this.updateCursor();
        });
        canvas.addEventListener("pointerup", () => this.end());
        canvas.addEventListener("pointercancel", () => this.end());
        canvas.addEventListener("contextmenu", event => event.preventDefault());
        canvas.addEventListener("wheel", event => {
            if (!this.image) return;
            event.preventDefault();
            const point = this.point(event), previous = this.scale;
            this.scale = Math.min(16, Math.max(0.02, this.scale * Math.exp(-event.deltaY * 0.001)));
            this.offset.x = point.x - (point.x - this.offset.x) * this.scale / previous;
            this.offset.y = point.y - (point.y - this.offset.y) * this.scale / previous;
            this.render();
        }, { passive: false });
        window.addEventListener("keydown", event => {
            const target = event.target;
            if (target && (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable)) return;
            if ((event.ctrlKey || event.metaKey) && !event.altKey && (this.hovered || document.activeElement === canvas)) {
                const key = event.key.toLowerCase();
                if (!event.shiftKey && key === "z") { event.preventDefault(); this.end(); this.undo(); return; }
                if (key === "y" || (event.shiftKey && key === "z")) { event.preventDefault(); this.end(); this.redo(); return; }
            }
            if (event.code === "Space") { this.space = true; event.preventDefault(); this.updateCursor(); }
        });
        window.addEventListener("keyup", event => { if (event.code === "Space") { this.space = false; this.updateCursor(); } });
        window.addEventListener("blur", () => { this.space = false; this.hovered = false; this.end(); this.updateCursor(); });
    }
    setImage(image, maskImage) {
        this.image = image;
        this.mask.width = this.tint.width = image.naturalWidth;
        this.mask.height = this.tint.height = image.naturalHeight;
        if (maskImage) {
            this.paint.drawImage(maskImage, 0, 0);
            const data = this.paint.getImageData(0, 0, this.mask.width, this.mask.height);
            for (let i = 0; i < data.data.length; i += 4) {
                data.data[i + 3] = data.data[i];
                data.data[i] = data.data[i + 1] = data.data[i + 2] = 255;
            }
            this.paint.putImageData(data, 0, 0);
        }
        this.history = []; this.future = []; this.bounds = null;
        this.historyLimit = Math.max(1, Math.min(15, Math.floor(48 * 1024 * 1024 / (this.mask.width * this.mask.height * 4))));
        this.fit();
    }
    point(event) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }
    imagePoint(point) {
        return { x: (point.x - this.offset.x) / this.scale, y: (point.y - this.offset.y) / this.scale };
    }
    updateCursor() {
        const painting = !!this.image && this.editable && this.hovered;
        const panning = this.space || this.drag?.pan;
        this.canvas.style.cursor = this.image && this.hovered && panning ? (this.drag?.pan ? "grabbing" : "grab") : painting ? "none" : "";
        const show = painting && !panning && this.pointer;
        this.cursor.style.display = show ? "block" : "none";
        if (show) this.placeCursor();
    }
    placeCursor() {
        const size = this.brushSize * this.scale;
        const rect = this.canvas.getBoundingClientRect(), stage = this.stage.getBoundingClientRect();
        this.cursor.style.width = this.cursor.style.height = size + "px";
        this.cursor.style.left = rect.left - stage.left + this.pointer.x - size / 2 + "px";
        this.cursor.style.top = rect.top - stage.top + this.pointer.y - size / 2 + "px";
    }
    fit() {
        if (!this.image) return;
        const rect = this.canvas.getBoundingClientRect();
        this.scale = Math.min((rect.width - 32) / this.mask.width, (rect.height - 32) / this.mask.height);
        this.offset = { x: (rect.width - this.mask.width * this.scale) / 2, y: (rect.height - this.mask.height * this.scale) / 2 };
        this.render();
    }
    snapshot() { return this.paint.getImageData(0, 0, this.mask.width, this.mask.height); }
    checkpoint() {
        if (this.historyLimit > 0) {
            this.history.push(this.snapshot());
            while (this.history.length > this.historyLimit) this.history.shift();
        }
        this.future = [];
    }
    start(event) {
        if (!this.image || ![0, 1].includes(event.button)) return;
        const pan = event.button === 1 || this.space;
        if (!pan && !this.editable) return;
        event.preventDefault();
        this.canvas.setPointerCapture(event.pointerId);
        const point = this.point(event);
        this.drag = { pan, last: point };
        if (!pan) {
            this.checkpoint();
            const p = this.imagePoint(point);
            this.stroke(p, p);
        }
        this.updateCursor();
    }
    move(event) {
        if (!this.drag) return;
        const point = this.point(event);
        if (this.drag.pan) {
            this.offset.x += point.x - this.drag.last.x;
            this.offset.y += point.y - this.drag.last.y;
        } else this.stroke(this.imagePoint(this.drag.last), this.imagePoint(point));
        this.drag.last = point;
        this.render();
    }
    stroke(from, to) {
        this.paint.globalCompositeOperation = this.tool === "eraser" ? "destination-out" : "source-over";
        this.paint.strokeStyle = this.paint.fillStyle = "white";
        this.paint.lineWidth = this.brushSize;
        this.paint.lineCap = this.paint.lineJoin = "round";
        this.paint.beginPath();
        this.paint.moveTo(from.x, from.y);
        this.paint.lineTo(to.x, to.y);
        this.paint.stroke();
        this.paint.beginPath();
        this.paint.arc(to.x, to.y, this.brushSize / 2, 0, 2 * Math.PI);
        this.paint.fill();
        this.paint.globalCompositeOperation = "source-over";
        this.render();
    }
    end() {
        if (!this.drag) return;
        const changed = !this.drag.pan;
        this.drag = null;
        if (changed) this.onChange();
        this.updateCursor();
    }
    clear() {
        if (!this.image || !this.editable) return;
        this.checkpoint();
        this.paint.clearRect(0, 0, this.mask.width, this.mask.height);
        this.render(); this.onChange();
    }
    undo() {
        if (!this.editable || !this.history.length) return;
        this.future.push(this.snapshot());
        this.paint.putImageData(this.history.pop(), 0, 0);
        this.render(); this.onChange();
    }
    redo() {
        if (!this.editable || !this.future.length) return;
        this.history.push(this.snapshot());
        this.paint.putImageData(this.future.pop(), 0, 0);
        this.render(); this.onChange();
    }
    blob() {
        const output = document.createElement("canvas");
        output.width = this.mask.width; output.height = this.mask.height;
        const ctx = output.getContext("2d");
        ctx.fillStyle = "black"; ctx.fillRect(0, 0, output.width, output.height);
        ctx.drawImage(this.mask, 0, 0);
        return new Promise((resolve, reject) => output.toBlob(blob => blob ? resolve(blob) : reject(new Error("Mask could not be encoded.")), "image/png"));
    }
    render() {
        this.updateCursor();
        const rect = this.canvas.getBoundingClientRect(), ratio = devicePixelRatio || 1;
        const width = Math.round(rect.width * ratio), height = Math.round(rect.height * ratio);
        if (this.canvas.width !== width || this.canvas.height !== height) {
            this.canvas.width = width; this.canvas.height = height;
        }
        const ctx = this.ctx;
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, rect.width, rect.height);
        if (!this.image) return;
        ctx.save(); ctx.translate(this.offset.x, this.offset.y); ctx.scale(this.scale, this.scale);
        ctx.drawImage(this.image, 0, 0);
        const tint = this.tint.getContext("2d");
        tint.clearRect(0, 0, this.tint.width, this.tint.height);
        tint.drawImage(this.mask, 0, 0);
        tint.globalCompositeOperation = "source-in";
        tint.fillStyle = "#ff705f"; tint.fillRect(0, 0, this.tint.width, this.tint.height);
        tint.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.4; ctx.drawImage(this.tint, 0, 0); ctx.globalAlpha = 1;
        if (this.bounds) {
            ctx.strokeStyle = "#7bdfc7"; ctx.lineWidth = 2 / this.scale;
            const [x, y, right, bottom] = this.bounds;
            ctx.strokeRect(x, y, right - x, bottom - y);
        }
        ctx.restore();
        this.onView(Math.round(this.scale * 100));
    }
}
