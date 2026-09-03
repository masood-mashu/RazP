"""
Vercel Serverless Function entry point for RazP API.
Exports the FastAPI instance directly for Vercel's ASGI Python runtime.
"""
import sys
import os

# Ensure the project root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Auto-detect Vercel environment
os.environ.setdefault("VERCEL", "1")

# Default to in-memory fallback on Vercel if DATABASE_URL is not configured
if "DATABASE_URL" not in os.environ and "RAZP_DEMO_IN_MEMORY" not in os.environ:
    os.environ["RAZP_DEMO_IN_MEMORY"] = "true"

# Export the FastAPI instance directly so Vercel detects isinstance(app, FastAPI)
from server.app import app
