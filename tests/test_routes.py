import asyncio
import io

from aiohttp import FormData, web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from local_edit_helper.comfy.routes import create_routes
from local_edit_helper.comfy import routes as routes_module
from pathlib import Path
from local_edit_helper.core.jobs import JobStore


def png(color):
    data = io.BytesIO()
    Image.new("RGB", (80, 80), color).save(data, format="PNG")
    return data.getvalue()


def test_http_round_trip(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(routes_module, "open_local_folder", lambda path: opened.append(path))
    async def run():
        app = web.Application()
        app.add_routes(create_routes(JobStore(tmp_path), tmp_path))
        async with TestClient(TestServer(app)) as client:
            response = await client.post("/gpt-local-edit/jobs", json={})
            assert response.status == 403
            headers = {"X-Local-Edit": "1"}
            form = FormData()
            form.add_field("image", png("gray"), filename="source.png")
            response = await client.post("/gpt-local-edit/jobs", data=form, headers=headers)
            assert response.status == 200
            job = (await response.json())["job"]
            base = "/gpt-local-edit/jobs/" + job["id"]
            form = FormData()
            form.add_field("mask", png("white"), filename="mask.png")
            form.add_field("settings", "{}")
            form.add_field("revision", str(job["revision"]))
            response = await client.post(base + "/preview", data=form, headers=headers)
            assert response.status == 200
            job = (await response.json())["job"]
            response = await client.post(base + "/prepare", json={"revision": job["revision"], "prompt": "Edit blue"}, headers=headers)
            job = (await response.json())["job"]
            form = FormData()
            form.add_field("image", png("blue"), filename="returned.png")
            form.add_field("policy", "strict")
            form.add_field("revision", str(job["revision"]))
            response = await client.post(base + "/import", data=form, headers=headers)
            assert response.status == 200
            job = (await response.json())["job"]
            response = await client.post(base + "/composite", json={"revision": job["revision"], "color_enabled": False, "mask_expansion": 4}, headers=headers)
            assert response.status == 200
            job = (await response.json())["job"]
            response = await client.post(base + "/finalize", json={"revision": job["revision"]}, headers=headers)
            assert response.status == 200
            response = await client.get(base + "/files/final.png")
            assert response.status == 200
            assert Image.open(io.BytesIO(await response.read())).size == (80, 80)
            current = (await (await client.get(base)).json())["job"]
            response = await client.post(base + "/open-handoff", json={"revision": current["revision"]}, headers=headers)
            assert response.status == 200
            directory = Path((await response.json())["directory"])
            assert opened == [directory]
            assert {p.name for p in directory.iterdir()} == {"01-crop.png", "02-overlay.png", "prompt.txt"}
            assert (directory / "prompt.txt").read_text() == "Edit blue"
            assert Image.open(directory / "01-crop.png").size == Image.open(directory / "02-overlay.png").size
            response = await client.post(base + "/open-handoff", json={"revision": current["revision"], "path": "C:/"}, headers=headers)
            assert response.status == 400 and len(opened) == 1
            response = await client.post(base + "/sent", json={"revision": 0}, headers=headers)
            assert response.status == 409
            response = await client.post(base + "/prompt", json={"request": "Edit"}, headers={**headers, "Origin": "https://evil.example"})
            assert response.status == 403
            response = await client.get(base)
            current = (await response.json())["job"]
            response = await client.post(base + "/rework", json={"revision": current["revision"], "step": "prompt", "prompt": current["prompt"]}, headers=headers)
            assert response.status == 200
            current = (await response.json())["job"]
            assert current["state"] == "DRAFT" and current["prompt"] == "Edit blue"
            response = await client.post(base + "/undo-rework", json={"revision": current["revision"], "prompt": ""}, headers=headers)
            assert response.status == 200
            assert (await response.json())["job"]["state"] == "FINALIZED"
            response = await client.get(base + "/files/private.txt")
            assert response.status == 404
    asyncio.run(run())
