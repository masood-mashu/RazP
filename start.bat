@echo off
TITLE RazP Sentinel - Autonomous Recovery Engine
echo ======================================================================
echo   RazP Sentinel: Autonomous Zero-Loss Payment Recovery Engine
echo   Razorpay AI Buildathon 2026 (Track 03)
echo ======================================================================
echo.

set DATABASE_URL=postgresql://postgres@127.0.0.1:5433/razp_test
set RAZP_DEMO_IN_MEMORY=false

echo [1/3] Ensuring PostgreSQL test cluster is active on port 5433...
python scripts\setup_test_db.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] PostgreSQL cluster startup returned non-zero. Attempting fallback...
)

echo.
echo [2/3] Verifying database connectivity...
python scripts\check_db.py
if %ERRORLEVEL% NEQ 0 (
    echo [NOTICE] Switching to high-speed in-memory demo mode...
    set RAZP_DEMO_IN_MEMORY=true
)

echo.
echo [3/3] Launching RazP Sentinel Server on http://127.0.0.1:8000 ...
echo       Press CTRL+C to stop.
echo.
start "" "http://127.0.0.1:8000"
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000

pause
