"""Migration utility to transfer local SQLite data to production Supabase PostgreSQL."""
import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publisher.config import load_env

load_env()
DB_PATH = PROJECT_ROOT / "trend_engine" / "data" / "trends.db"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_sqlite_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def export_sqlite_to_json():
    """Exports SQLite tables to in-memory dictionaries for migration."""
    conn = get_sqlite_conn()
    c = conn.cursor()
    data = {}

    tables = ["reels", "reel_analyses", "adsync_ideas", "competitors", "video_catalog", "reel_publications"]
    for t in tables:
        try:
            c.execute(f"SELECT * FROM {t}")
            rows = [dict(r) for r in c.fetchall()]
            data[t] = rows
            print(f"Extracted {len(rows)} records from SQLite table '{t}'")
        except Exception as e:
            print(f"Skipping table {t}: {e}")

    conn.close()
    return data


def migrate_via_direct_postgres(data):
    """Direct bulk copy if DATABASE_URL is configured."""
    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        print("psycopg2 not installed, install psycopg2-binary to use direct Postgres migration.")
        return False

    print("Connecting to Supabase PostgreSQL via DATABASE_URL...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Create tables if not exist
    schema_sql_path = PROJECT_ROOT / "scripts" / "supabase_schema.sql"
    if schema_sql_path.exists():
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            cur.execute(f.read())
        conn.commit()

    # Insert data
    for table, rows in data.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_names = ", ".join(cols)
        placeholders = ", ".join([f"%({c})s" for c in cols])
        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        execute_batch(cur, query, rows)
        conn.commit()
        print(f"Successfully migrated {len(rows)} rows into PostgreSQL table '{table}'")

    cur.close()
    conn.close()
    return True


def migrate_via_postgrest(data):
    """Fallback migration via PostgREST bulk insert API."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL and SUPABASE_KEY are required for PostgREST migration.")
        return False

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates"
    }

    for table, rows in data.items():
        if not rows:
            continue
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        req = urllib.request.Request(url, data=json.dumps(rows).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"PostgREST: Migrated {len(rows)} records into '{table}' (HTTP {resp.status})")
        except urllib.error.HTTPError as e:
            print(f"PostgREST migration error for '{table}': HTTP {e.code} - {e.read().decode('utf-8', errors='replace')}")

    return True


def run_migration():
    print("=" * 65)
    print(" 🔄 Starting AdSync SQLite -> Supabase PostgreSQL Data Migration")
    print("=" * 65)
    data = export_sqlite_to_json()

    if DATABASE_URL:
        success = migrate_via_direct_postgres(data)
        if success:
            print("Direct Postgres migration completed successfully!")
            return

    print("Attempting PostgREST bulk migration...")
    migrate_via_postgrest(data)
    print("=" * 65)


if __name__ == "__main__":
    run_migration()
