"""
Automated Test Database Provisioner for RazP.
Manages a portable, isolated PostgreSQL test cluster for local execution.
"""
from __future__ import annotations
import os
import sys
import time
import shutil
import zipfile
import urllib.request
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PG_DIR = BASE_DIR / ".pg_test"
PG_DATA = PG_DIR / "data"
PG_LOG = PG_DIR / "postgres.log"
PORT = 5433
DB_NAME = "razp_test"
USER = "postgres"

ZIP_URL = "https://get.enterprisedb.com/postgresql/postgresql-16.8-1-windows-x64-binaries.zip"


def find_pg_bin() -> Optional[Path]:
    """Finds initdb and pg_ctl in common paths or portable directory."""
    # 1. Check local portable directory
    local_bin = PG_DIR / "pgsql" / "bin"
    if (local_bin / "initdb.exe").exists() and (local_bin / "pg_ctl.exe").exists():
        return local_bin

    # 2. Check standard Program Files installations
    for version in ["17", "16", "15", "14"]:
        candidate = Path(f"C:/Program Files/PostgreSQL/{version}/bin")
        if (candidate / "initdb.exe").exists() and (candidate / "pg_ctl.exe").exists():
            return candidate

    # 3. Check system PATH
    initdb_path = shutil.which("initdb")
    if initdb_path:
        return Path(initdb_path).parent

    return None


def download_and_extract_portable_pg() -> Path:
    """Downloads portable Windows x64 PostgreSQL binaries and extracts them."""
    PG_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PG_DIR / "postgresql-binaries.zip"
    
    if not (PG_DIR / "pgsql" / "bin" / "initdb.exe").exists():
        print(f"[setup_test_db] Downloading portable PostgreSQL from {ZIP_URL}...")
        
        # Download with progress report
        def report(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 // total_size)
                if block_num % 1000 == 0 or percent == 100:
                    print(f"[setup_test_db] Download: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")

        urllib.request.urlretrieve(ZIP_URL, zip_path, reporthook=report)
        print("[setup_test_db] Extracting PostgreSQL binaries...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(PG_DIR)
        
        if zip_path.exists():
            zip_path.unlink()
        print("[setup_test_db] Extraction complete.")

    return PG_DIR / "pgsql" / "bin"


def start_test_db() -> str:
    """Initializes and starts the isolated PostgreSQL test instance."""
    pg_bin = find_pg_bin()
    if not pg_bin:
        print("[setup_test_db] PostgreSQL binaries not found on system. Downloading portable package...")
        pg_bin = download_and_extract_portable_pg()

    print(f"[setup_test_db] Using PostgreSQL binaries at: {pg_bin}")

    # Check if already running
    status_cmd = [str(pg_bin / "pg_ctl.exe"), "status", "-D", str(PG_DATA)]
    res = subprocess.run(status_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[setup_test_db] PostgreSQL is already running on port {PORT}.")
        return f"postgresql://{USER}@{USER}:password@localhost:{PORT}/{DB_NAME}"

    # Initialize cluster if data directory doesn't exist
    if not (PG_DATA / "PG_VERSION").exists():
        print(f"[setup_test_db] Initializing database cluster at {PG_DATA}...")
        init_cmd = [
            str(pg_bin / "initdb.exe"),
            "-D", str(PG_DATA),
            "-U", USER,
            "-A", "trust",
            "--encoding=UTF8",
            "--locale=C"
        ]
        subprocess.run(init_cmd, check=True)

    # Start PostgreSQL daemon
    print(f"[setup_test_db] Starting PostgreSQL on port {PORT}...")
    start_cmd = [
        str(pg_bin / "pg_ctl.exe"),
        "start",
        "-D", str(PG_DATA),
        "-l", str(PG_LOG),
        "-o", f"-p {PORT}"
    ]
    subprocess.run(start_cmd, check=True)

    # Wait for postgres to accept connections
    time.sleep(2)

    # Create database if needed
    createdb_cmd = [
        str(pg_bin / "createdb.exe"),
        "-p", str(PORT),
        "-U", USER,
        DB_NAME
    ]
    subprocess.run(createdb_cmd, capture_output=True)  # OK if already exists

    db_url = f"postgresql://{USER}@localhost:{PORT}/{DB_NAME}"
    print(f"[setup_test_db] PostgreSQL test database ready at: {db_url}")
    return db_url


def stop_test_db():
    """Stops the test PostgreSQL daemon."""
    pg_bin = find_pg_bin()
    if not pg_bin or not PG_DATA.exists():
        return

    stop_cmd = [
        str(pg_bin / "pg_ctl.exe"),
        "stop",
        "-D", str(PG_DATA),
        "-m", "fast"
    ]
    subprocess.run(stop_cmd, capture_output=True)
    print("[setup_test_db] Test database stopped.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_test_db()
    else:
        url = start_test_db()
        print(f"DATABASE_URL={url}")
