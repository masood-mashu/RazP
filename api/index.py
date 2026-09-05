"""
Vercel Serverless Function entry point for RazP API.
Exports the FastAPI instance directly for Vercel's ASGI Python runtime.
Fails closed in production if database durability requirements are not satisfied.
"""
import sys
import os

# Ensure the project root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Auto-detect Vercel environment
os.environ.setdefault("VERCEL", "1")

# Detect database URL from standard DATABASE_URL or Supabase integration (POSTGRES_URL)
db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_PRISMA_URL") or os.getenv("SUPABASE_DATABASE_URL")
if db_url and "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = db_url

is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or os.getenv("VERCEL_ENV") == "production"

# Fail closed in production: Never silently switch to ephemeral in-memory mode
if is_prod and not db_url:
    raise RuntimeError(
        "FATAL: Running in production environment (VERCEL_ENV=production or ENVIRONMENT=production) "
        "but DATABASE_URL is not configured. RazP requires PostgreSQL durability in production. "
        "Automatic in-memory fallback is prohibited."
    )

# Explicit opt-in for demo in-memory fallback only in non-production
if not db_url and "RAZP_DEMO_IN_MEMORY" not in os.environ:
    os.environ["RAZP_DEMO_IN_MEMORY"] = "true"

# Export the FastAPI instance directly so Vercel detects isinstance(app, FastAPI)
from server.app import app
