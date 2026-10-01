from pathlib import Path

from server import PromptServer

from .src.local_edit_helper.comfy.integration import store
from .src.local_edit_helper.comfy.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .src.local_edit_helper.comfy.routes import create_routes

WEB_DIRECTORY = "./web/extension"
for route in create_routes(store, Path(__file__).parent / "web"):
    PromptServer.instance.routes.route(route.method, route.path, **route.kwargs)(route.handler)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
