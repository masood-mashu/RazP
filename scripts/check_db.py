import psycopg2

conn = psycopg2.connect("postgresql://postgres@127.0.0.1:5433/postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT version();")
pg_version = cur.fetchone()[0]
print("PostgreSQL Version:", pg_version)

cur.execute("SELECT 1 FROM pg_database WHERE datname='razp_test';")
if not cur.fetchone():
    cur.execute("CREATE DATABASE razp_test;")
    print("Created database razp_test.")
else:
    print("Database razp_test already exists.")

conn.close()

# Test connecting to razp_test
conn_test = psycopg2.connect("postgresql://postgres@127.0.0.1:5433/razp_test")
print("Successfully connected to postgresql://postgres@127.0.0.1:5433/razp_test")
conn_test.close()
