"""
Unpacks embedded postgres binaries from jar into .pg_test/pgsql.
"""
import os
import io
import lzma
import tarfile
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JAR_PATH = BASE_DIR / ".pg_test" / "pg-binaries.jar"
DEST_DIR = BASE_DIR / ".pg_test" / "pgsql"


def unpack():
    if not JAR_PATH.exists():
        raise FileNotFoundError(f"Jar not found at {JAR_PATH}")

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Opening jar: {JAR_PATH}...")
    with zipfile.ZipFile(JAR_PATH, "r") as z:
        # Find the .txz or .tar.xz file inside jar
        txz_name = [name for name in z.namelist() if name.endswith(".txz") or name.endswith(".tar.xz")]
        if not txz_name:
            print(f"Files inside jar: {z.namelist()[:10]}")
            # If plain files
            z.extractall(DEST_DIR)
            print("Extracted directly from jar.")
            return

        print(f"Found archive inside jar: {txz_name[0]}")
        txz_bytes = z.read(txz_name[0])
        
        print("Decompressing XZ archive...")
        with lzma.open(io.BytesIO(txz_bytes)) as xz_file:
            with tarfile.open(fileobj=xz_file) as tar:
                tar.extractall(DEST_DIR)
        print(f"Successfully extracted PostgreSQL binaries to {DEST_DIR}.")


if __name__ == "__main__":
    unpack()
