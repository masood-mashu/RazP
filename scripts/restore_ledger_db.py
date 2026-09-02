import os, sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from core.persistence import PersistenceManager

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5433/razp_test")
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("UPDATE audit_blocks SET action_executed = 'SCHEDULE_PTP' WHERE block_index = 0;")
conn.commit()

pm = PersistenceManager(db_url=db_url)
valid, err = pm.verify_persisted_ledger_integrity()
print(f"Ledger valid: {valid}, error: {err}")
