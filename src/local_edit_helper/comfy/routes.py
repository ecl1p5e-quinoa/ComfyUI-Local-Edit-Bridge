"""Local HTTP adapter; all image operations run off the aiohttp event loop."""
import asyncio
import json
import os
import sys
import subprocess
from ipaddress import ip_address
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web

from ..bridge.manual import MAX_BYTES, ManualBridge
from ..core.jobs import ConflictError
from ..prompt.builder import build_prompt

BASE = "/gpt-local-edit"


def open_local_folder(path):
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


async def fields(request):
    result = {}
    if request.content_type == "multipart/form-data":
        reader = await request.multipart()
        total = 0
        async for part in reader:
            if not part.name or part.name in result:
                raise ValueError("Duplicate or unnamed form field.")
            data = bytearray()
            while chunk := await part.read_chunk(65536):
                data.extend(chunk)
                total += len(chunk)
                if total > MAX_BYTES + 65536:
                    raise ValueError("Upload exceeds 32 MiB.")
            result[part.name] = bytes(data) if part.filename else data.decode("utf-8")
        if "revision" in result:
            try:
                result["revision"] = int(result["revision"])
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid revision.") from exc
        if "settings" in result:
            result["settings"] = json.loads(result["settings"])
        return result
    if request.content_type != "application/json":
        raise ValueError("Use JSON or multipart form data.")
    data = bytearray()
    async for chunk in request.content.iter_chunked(65536):
        data.extend(chunk)
        if len(data) > 65536:
            raise ValueError("JSON request is too large.")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("JSON body must be an object.")
    return result


def require_fields(data, required, optional=()):
    if set(data) - set(required) - set(optional) or set(required) - set(data):
        raise ValueError("Missing or unexpected request fields.")


def endpoint(function):
    @wraps(function)
    async def guarded(request):
        try:
            if request.method == "POST":
                origin = request.headers.get("Origin")
                if request.headers.get("X-Local-Edit") != "1":
                    raise web.HTTPForbidden(text="Same-origin editor header required.")
                if origin and (urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme):
                    raise web.HTTPForbidden(text="Cross-origin editor request denied.")
                if request.headers.get("Sec-Fetch-Site") == "cross-site":
                    raise web.HTTPForbidden(text="Cross-site editor request denied.")
            return await function(request)
        except ConflictError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except FileNotFoundError:
            return web.json_response({"error": "Job or artifact not found."}, status=404)
        except OSError as exc:
            return web.json_response({"error": "Local job files could not be read or written: " + str(exc)}, status=500)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except web.HTTPException as exc:
            return web.json_response({"error": exc.text}, status=exc.status)
    return guarded


def create_routes(store, web_directory):
    routes = web.RouteTableDef()
    bridge = ManualBridge(store)
    web_directory = Path(web_directory)

    def response(job):
        return web.json_response({"job": job, "directory": str(store.directory(job["id"]))})

    @routes.get(BASE + "/editor")
    async def editor(request):
        return web.FileResponse(web_directory / "index.html", headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'self'",
        })

    @routes.get(BASE + "/assets/{name}")
    @endpoint
    async def asset(request):
        name = request.match_info["name"]
        if name not in {"editor.js", "canvas.js", "api.js", "editor.css"}:
            raise FileNotFoundError()
        return web.FileResponse(web_directory / name, headers={"Cache-Control": "no-store"})

    @routes.get(BASE + "/jobs")
    @endpoint
    async def listing(request):
        return web.json_response(await asyncio.to_thread(store.listing))

    @routes.post(BASE + "/jobs")
    @endpoint
    async def create(request):
        data = await fields(request)
        require_fields(data, {"image"})
        if not isinstance(data["image"], bytes):
            raise ValueError("Choose an image file.")
        return response(await asyncio.to_thread(bridge.create, data["image"]))

    @routes.get(BASE + "/jobs/{job_id}")
    @endpoint
    async def get_job(request):
        def load_current():
            with store.lock:
                job = store.read(request.match_info["job_id"])
                store.prune(job)
                return job
        return response(await asyncio.to_thread(load_current))

    @routes.get(BASE + "/jobs/{job_id}/files/{name}")
    @endpoint
    async def artifact(request):
        path = await asyncio.to_thread(store.artifact, request.match_info["job_id"], request.match_info["name"])
        if not path.is_file():
            raise FileNotFoundError()
        return web.FileResponse(path, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @routes.post(BASE + "/jobs/{job_id}/open-handoff")
    @endpoint
    async def open_handoff(request):
        if not request.remote or not ip_address(request.remote).is_loopback:
            raise web.HTTPForbidden(text="Open the editor on this computer to open its handoff folder.")
        data = await fields(request)
        require_fields(data, {"revision"})
        def export_and_open():
            with store.lock:
                directory = store.export_handoff(request.match_info["job_id"], data["revision"])
                open_local_folder(directory)
                return str(directory)
        directory = await asyncio.to_thread(export_and_open)
        return web.json_response({"directory": directory})

    @routes.post(BASE + "/jobs/{job_id}/preview")
    @endpoint
    async def preview(request):
        data = await fields(request)
        require_fields(data, {"revision", "mask", "settings"})
        if not isinstance(data["mask"], bytes):
            raise ValueError("Choose a PNG mask.")
        job = await asyncio.to_thread(bridge.preview, request.match_info["job_id"],
                                      data["revision"], data["mask"], data["settings"])
        return response(job)

    @routes.post(BASE + "/jobs/{job_id}/prompt")
    @endpoint
    async def prompt(request):
        await asyncio.to_thread(store.read, request.match_info["job_id"])
        data = await fields(request)
        require_fields(data, {"request"}, {"context"})
        return web.json_response({"prompt": build_prompt(data["request"], data.get("context", ""))})

    @routes.post(BASE + "/jobs/{job_id}/prepare")
    @endpoint
    async def prepare(request):
        data = await fields(request)
        require_fields(data, {"revision", "prompt"})
        return response(await asyncio.to_thread(bridge.prepare, request.match_info["job_id"],
                                                data["revision"], data["prompt"]))

    @routes.post(BASE + "/jobs/{job_id}/rework")
    @endpoint
    async def rework(request):
        data = await fields(request)
        require_fields(data, {"revision", "step", "prompt"}, {"prompt_inputs"})
        return response(await asyncio.to_thread(bridge.rework, request.match_info["job_id"], **data))

    @routes.post(BASE + "/jobs/{job_id}/undo-rework")
    @endpoint
    async def undo_rework(request):
        data = await fields(request)
        require_fields(data, {"revision", "prompt"}, {"prompt_inputs"})
        return response(await asyncio.to_thread(bridge.undo_rework, request.match_info["job_id"], **data))

    @routes.post(BASE + "/jobs/{job_id}/sent")
    @endpoint
    async def sent(request):
        data = await fields(request)
        require_fields(data, {"revision"})
        return response(await asyncio.to_thread(bridge.sent, request.match_info["job_id"], data["revision"]))

    @routes.post(BASE + "/jobs/{job_id}/import")
    @endpoint
    async def import_result(request):
        data = await fields(request)
        require_fields(data, {"revision", "image", "policy"})
        if not isinstance(data["image"], bytes):
            raise ValueError("Choose an image file.")
        return response(await asyncio.to_thread(bridge.import_result, request.match_info["job_id"],
                                                data["revision"], data["image"], data["policy"]))

    @routes.post(BASE + "/jobs/{job_id}/composite")
    @endpoint
    async def process(request):
        data = await fields(request)
        require_fields(data, {"revision"}, {"color_enabled", "strength", "feather", "seam_width", "debug", "mask_expansion"})
        return response(await asyncio.to_thread(bridge.process, request.match_info["job_id"], **data))

    @routes.post(BASE + "/jobs/{job_id}/finalize")
    @endpoint
    async def finalize(request):
        data = await fields(request)
        require_fields(data, {"revision"})
        return response(await asyncio.to_thread(bridge.finalize, request.match_info["job_id"], data["revision"]))

    return routes
