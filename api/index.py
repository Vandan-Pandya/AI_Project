"""
Vercel Serverless Function entrypoint for FastAPI.
Normalizes request paths to handle Vercel proxying and rewrites seamlessly.
"""

from __future__ import annotations
import sys
from pathlib import Path
from starlette.types import ASGIApp, Scope, Receive, Send

# Add project root directory to sys.path so app modules import cleanly on Vercel
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import app as fastapi_app


class VercelPathNormalizer:
    """
    ASGI middleware ensuring routes match regardless of how Vercel proxies the request.
    If Vercel forwards a path prefixed with /api/index or /api/index.py, this strips
    the prefix so FastAPI route handlers (/docs, /health, /auth, etc.) match directly.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            for prefix in ("/api/index.py", "/api/index"):
                if path == prefix:
                    scope["path"] = "/"
                    break
                elif path.startswith(prefix + "/"):
                    scope["path"] = path[len(prefix):]
                    break
        await self.app(scope, receive, send)


app = VercelPathNormalizer(fastapi_app)
