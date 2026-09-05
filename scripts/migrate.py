"""
RazP Schema Migration Runner
Applies ordered SQL migrations from the `migrations/` directory against PostgreSQL.
"""
from __future__ import annotations
import os
import sys
import glob
from pathlib import Path
from typing import Optional, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2


def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_PRISMA_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL (or POSTGRES_URL) environment variable is required to run migrations.")
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    return db_url


def run_migrations(db_url: Optional[str] = None, migrations_dir: Optional[str] = None) -> List[str]:
    """
    Executes unapplied migrations in ascending order. Returns list of applied migration names.
    """
    url = db_url or get_db_url()
    
    if not migrations_dir:
        base_dir = Path(__file__).resolve().parent.parent
        migrations_dir = str(base_dir / "migrations")
        
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    if not migration_files:
        print(f"[migrate] No migration files found in {migrations_dir}")
        return []

    applied: List[str] = []
    
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            # Ensure schema_migrations table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     TEXT PRIMARY KEY,
                    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()

            cur.execute("SELECT version FROM schema_migrations;")
            already_applied = {row[0] for row in cur.fetchall()}

            for filepath in migration_files:
                filename = os.path.basename(filepath)
                version_key = os.path.splitext(filename)[0]

                if version_key in already_applied:
                    print(f"[migrate] Skipping already applied migration: {filename}")
                    continue

                print(f"[migrate] Applying migration: {filename}...")
                with open(filepath, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # Execute migration SQL
                cur.execute(sql_content)
                # Ensure recorded if SQL did not insert it itself
                cur.execute("""
                    INSERT INTO schema_migrations (version)
                    VALUES (%s)
                    ON CONFLICT (version) DO NOTHING;
                """, (version_key,))
                
                conn.commit()
                applied.append(version_key)
                print(f"[migrate] Successfully applied: {filename}")

        return applied
    except Exception as exc:
        conn.rollback()
        print(f"[migrate] ERROR applying migrations: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        applied_list = run_migrations()
        print(f"[migrate] Migration complete. Applied {len(applied_list)} migrations.")
    except Exception as err:
        sys.exit(1)
