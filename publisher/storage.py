"""Database storage and publication history ledger for Instagram Reels."""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class PublisherDatabase:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS reel_publications (
                    publication_id TEXT PRIMARY KEY,
                    video_path TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    hashtags_json TEXT NOT NULL,
                    creation_id TEXT,
                    post_id TEXT,
                    permalink TEXT,
                    status TEXT NOT NULL, -- PENDING, UPLOADED, PUBLISHED, SCHEDULED, FAILED, DRY_RUN
                    scheduled_time INTEGER, -- Unix timestamp in seconds
                    is_dry_run INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    response_payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_publication(
        self,
        pub_id: str,
        video_path: str,
        caption: str,
        hashtags: List[str],
        status: str,
        is_dry_run: bool,
        creation_id: Optional[str] = None,
        post_id: Optional[str] = None,
        permalink: Optional[str] = None,
        scheduled_time: Optional[int] = None,
        error_message: Optional[str] = None,
        response_payload: Optional[Dict[str, Any]] = None
    ) -> str:
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO reel_publications (
                    publication_id, video_path, caption, hashtags_json,
                    creation_id, post_id, permalink, status, scheduled_time,
                    is_dry_run, error_message, response_payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                pub_id,
                video_path,
                caption,
                json.dumps(hashtags),
                creation_id,
                post_id,
                permalink,
                status,
                scheduled_time,
                1 if is_dry_run else 0,
                error_message,
                json.dumps(response_payload) if response_payload else None
            ))
            conn.commit()
        return pub_id

    def get_publication(self, pub_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM reel_publications WHERE publication_id = ?", (pub_id,))
            row = c.fetchone()
            if not row:
                return None
            res = dict(row)
            res["hashtags"] = json.loads(res["hashtags_json"]) if res.get("hashtags_json") else []
            return res

    def list_publications(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM reel_publications ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["hashtags"] = json.loads(item["hashtags_json"]) if item.get("hashtags_json") else []
                results.append(item)
            return results

