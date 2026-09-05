#!/usr/bin/env bash
# RazP Sentinel - Autonomous Zero-Loss Payment Recovery Engine
# Startup launcher for Linux/macOS
set -e

echo "======================================================================"
echo "  RazP Sentinel: Autonomous Zero-Loss Payment Recovery Engine"
echo "  Razorpay AI Buildathon 2026 (Track 03)"
echo "======================================================================"
echo ""

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@127.0.0.1:5432/razp_test}"
export RAZP_DEMO_IN_MEMORY="${RAZP_DEMO_IN_MEMORY:-true}"

echo "[1/2] Checking database connectivity..."
python scripts/check_db.py || {
    echo "[NOTICE] Local PostgreSQL not running on 5433/5432. Defaulting to in-memory demo mode."
    export RAZP_DEMO_IN_MEMORY="true"
}

echo ""
echo "[2/2] Launching RazP Sentinel Server on http://127.0.0.1:8000 ..."
echo "      Press CTRL+C to stop."
echo ""
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
