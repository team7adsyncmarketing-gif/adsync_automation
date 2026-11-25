"""Unified database adapter for AdSync supporting both Supabase PostgreSQL and local SQLite."""
import os
import sqlite3
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "trend_engine" / "data" / "trends.db"


class DatabaseAdapter:
    def __init__(self, sqlite_path: Optional[Path] = None):
        self.sqlite_path = Path(sqlite_path or DEFAULT_SQLITE_PATH)
        self.database_url = os.environ.get("DATABASE_URL")
        self.is_postgres = bool(self.database_url)

    @contextmanager
    def get_connection(self):
        if self.is_postgres:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                conn = psycopg2.connect(self.database_url)
                try:
                    yield conn
                finally:
                    conn.close()
                return
            except Exception as e:
                print(f"[DatabaseAdapter] PostgreSQL connection error, falling back to SQLite: {e}")

        # SQLite fallback (Local development)
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
