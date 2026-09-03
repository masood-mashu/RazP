"""
Vercel Serverless Function entry point for RazP API.
This exports the FastAPI ASGI application for Vercel Python runtime.
"""
import sys
import os

# Ensure the project root directory is in sys.path so 'server', 'core', 'benchmark', 'prompts' are resolvable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Auto-detect Vercel environment
os.environ.setdefault("VERCEL", "1")

# Default to in-memory fallback on Vercel if DATABASE_URL is not configured
if "DATABASE_URL" not in os.environ and "RAZP_DEMO_IN_MEMORY" not in os.environ:
    os.environ["RAZP_DEMO_IN_MEMORY"] = "true"

from server.app import app as _base_app

# ASGI wrapper to handle both /api/xxx and /xxx paths seamlessly on Vercel
async def app(scope, receive, send):
    if scope.get("type") == "http":
        path = scope.get("path", "")
        # If the path arrived stripped of /api (e.g. /system/status), prepend /api
        # unless it is already /healthz or /
        if not path.startswith("/api") and path not in ("/", "/healthz"):
            scope = dict(scope)
            scope["path"] = f"/api{path}"
    await _base_app(scope, receive, send)
