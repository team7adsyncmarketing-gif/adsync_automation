"""SQLite persistence layer for AdSync Trend Engine."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any
from .models import ReelItem, ReelAnalysis, AdSyncIdea, CompetitorProfile, ReelSnapshot


class DatabaseRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize_schema(self):
        """Initializes tables for reels, analyses, and generated ideas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reels (
                reel_id TEXT PRIMARY KEY,
                shortcode TEXT,
                url TEXT,
                caption TEXT,
                author_username TEXT,
                author_full_name TEXT,
                play_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                hashtags TEXT,
                audio_id TEXT,
                audio_title TEXT,
                audio_artist TEXT,
                is_original_audio INTEGER DEFAULT 0,
                published_at TEXT,
                fetched_at TEXT,
                is_mock INTEGER DEFAULT 0,
                raw_json TEXT
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reel_analyses (
                reel_id TEXT PRIMARY KEY,
                primary_category TEXT,
                confidence_score REAL,
                hook_text TEXT,
                hook_type TEXT,
                hook_psychology TEXT,
                content_format TEXT,
                virality_score REAL,
                analyzed_at TEXT,
                FOREIGN KEY (reel_id) REFERENCES reels (reel_id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS adsync_ideas (
                idea_id TEXT PRIMARY KEY,
                source_reel_id TEXT,
                target_category TEXT,
                topic TEXT,
                hooks TEXT,
                target_audience TEXT,
                business_problem TEXT,
                content_format TEXT,
                faceless_short_style TEXT,
                call_to_action TEXT,
                opportunity_score REAL,
                reasoning TEXT,
                trend_reference_url TEXT,
                created_at TEXT,
                FOREIGN KEY (source_reel_id) REFERENCES reels (reel_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                handle TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                avatar_url TEXT,
                verified INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                follower_count INTEGER,
                following_count INTEGER,
                posts_count INTEGER,
                added_at TEXT,
                last_fetched_at TEXT,
                notes TEXT
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitor_reel_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                reel_id TEXT NOT NULL,
                handle TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                play_count INTEGER,
                like_count INTEGER,
                comment_count INTEGER,
                share_count INTEGER,
                FOREIGN KEY (reel_id) REFERENCES reels (reel_id) ON DELETE CASCADE,
                FOREIGN KEY (handle) REFERENCES competitors (handle) ON DELETE CASCADE
            );
            """)

            # Performance indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reels_mock ON reels(is_mock);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reels_likes ON reels(like_count DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_cat ON reel_analyses(primary_category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ideas_score ON adsync_ideas(opportunity_score DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comp_cat ON competitors(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_reel ON competitor_reel_snapshots(reel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_handle ON competitor_reel_snapshots(handle);")

            conn.commit()

    def save_reels(self, reels: List[ReelItem]) -> int:
        """Upserts a batch of ReelItem objects."""
        if not reels:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            inserted = 0
            for r in reels:
                cursor.execute("""
                INSERT INTO reels (
                    reel_id, shortcode, url, caption, author_username, author_full_name,
                    play_count, like_count, comment_count, share_count, hashtags,
                    audio_id, audio_title, audio_artist, is_original_audio,
                    published_at, fetched_at, is_mock, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reel_id) DO UPDATE SET
                    play_count = excluded.play_count,
                    like_count = excluded.like_count,
                    comment_count = excluded.comment_count,
                    share_count = excluded.share_count,
                    fetched_at = excluded.fetched_at;
                """, (
                    r.reel_id,
                    r.shortcode,
                    r.url,
                    r.caption,
                    r.author_username,
                    r.author_full_name,
                    r.play_count,
                    r.like_count,
                    r.comment_count,
                    r.share_count,
                    json.dumps(r.hashtags),
                    r.audio_id,
                    r.audio_title,
                    r.audio_artist,
                    1 if r.is_original_audio else 0,
                    r.published_at,
                    r.fetched_at,
                    1 if r.is_mock else 0,
                    r.raw_json,
                ))
                inserted += 1
            conn.commit()
            return inserted

    def save_analyses(self, analyses: List[ReelAnalysis]) -> int:
        """Upserts a batch of ReelAnalysis objects."""
        if not analyses:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            count = 0
            for a in analyses:
                cursor.execute("""
                INSERT INTO reel_analyses (
                    reel_id, primary_category, confidence_score, hook_text,
                    hook_type, hook_psychology, content_format, virality_score, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reel_id) DO UPDATE SET
                    primary_category = excluded.primary_category,
                    confidence_score = excluded.confidence_score,
                    hook_text = excluded.hook_text,
                    hook_type = excluded.hook_type,
                    hook_psychology = excluded.hook_psychology,
                    content_format = excluded.content_format,
                    virality_score = excluded.virality_score,
                    analyzed_at = excluded.analyzed_at;
                """, (
                    a.reel_id,
                    a.primary_category,
                    a.confidence_score,
                    a.hook_text,
                    a.hook_type,
                    a.hook_psychology,
                    a.content_format,
                    a.virality_score,
                    a.analyzed_at,
                ))
                count += 1
            conn.commit()
            return count

    def save_ideas(self, ideas: List[AdSyncIdea]) -> int:
        """Upserts a batch of AdSyncIdea objects."""
        if not ideas:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            count = 0
            for i in ideas:
                cursor.execute("""
                INSERT INTO adsync_ideas (
                    idea_id, source_reel_id, target_category, topic, hooks,
                    target_audience, business_problem, content_format,
                    faceless_short_style, call_to_action, opportunity_score,
                    reasoning, trend_reference_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idea_id) DO UPDATE SET
                    opportunity_score = excluded.opportunity_score,
                    reasoning = excluded.reasoning;
                """, (
                    i.idea_id,
                    i.source_reel_id,
                    i.target_category,
                    i.topic,
                    json.dumps(i.hooks),
                    i.target_audience,
                    i.business_problem,
                    i.content_format,
                    i.faceless_short_style,
                    i.call_to_action,
                    i.opportunity_score,
                    i.reasoning,
                    i.trend_reference_url,
                    i.created_at,
                ))
                count += 1
            conn.commit()
            return count

    def get_reels(self, is_mock: Optional[bool] = None, limit: int = 100) -> List[ReelItem]:
        """Retrieves stored reels, optionally filtered by mock status."""
        query = "SELECT * FROM reels"
        params = []
        if is_mock is not None:
            query += " WHERE is_mock = ?"
            params.append(1 if is_mock else 0)
        query += " ORDER BY play_count DESC, like_count DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            out = []
            for r in rows:
                out.append(ReelItem(
                    reel_id=r["reel_id"],
                    shortcode=r["shortcode"],
                    url=r["url"],
                    caption=r["caption"],
                    author_username=r["author_username"],
                    author_full_name=r["author_full_name"],
                    play_count=r["play_count"],
                    like_count=r["like_count"],
                    comment_count=r["comment_count"],
                    share_count=r["share_count"],
                    hashtags=json.loads(r["hashtags"] or "[]"),
                    audio_id=r["audio_id"],
                    audio_title=r["audio_title"],
                    audio_artist=r["audio_artist"],
                    is_original_audio=bool(r["is_original_audio"]),
                    published_at=r["published_at"],
                    fetched_at=r["fetched_at"],
                    is_mock=bool(r["is_mock"]),
                    raw_json=r["raw_json"],
                ))
            return out

    def get_top_ideas(self, is_mock: Optional[bool] = None, limit: int = 20) -> List[AdSyncIdea]:
        """Retrieves top AdSync ideas ranked by opportunity score, filtered by mock status."""
        query = """
            SELECT i.*
            FROM adsync_ideas i
        """
        params: List[Any] = []
        if is_mock is not None:
            query += """
                JOIN reels r ON i.source_reel_id = r.reel_id
                WHERE r.is_mock = ?
            """
            params.append(1 if is_mock else 0)

        query += " ORDER BY i.opportunity_score DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            out = []
            for r in rows:
                out.append(AdSyncIdea(
                    idea_id=r["idea_id"],
                    source_reel_id=r["source_reel_id"],
                    target_category=r["target_category"],
                    topic=r["topic"],
                    hooks=json.loads(r["hooks"] or "[]"),
                    target_audience=r["target_audience"],
                    business_problem=r["business_problem"],
                    content_format=r["content_format"],
                    faceless_short_style=r["faceless_short_style"],
                    call_to_action=r["call_to_action"],
                    opportunity_score=r["opportunity_score"],
                    reasoning=r["reasoning"],
                    trend_reference_url=r["trend_reference_url"],
                    created_at=r["created_at"],
                ))
            return out

    def get_summary_stats(self, is_mock: Optional[bool] = None) -> Dict[str, Any]:
        """Generates statistical overview of ingested trends, engagement telemetry, and metadata completeness."""
        with self._get_connection() as conn:
            where_reels = ""
            where_analyses = ""
            params = []
            if is_mock is not None:
                where_reels = " WHERE is_mock = ?"
                where_analyses = " WHERE r.is_mock = ?"
                params.append(1 if is_mock else 0)

            total_reels = conn.execute(f"SELECT COUNT(*) FROM reels{where_reels}", params).fetchone()[0]
            mock_reels = conn.execute("SELECT COUNT(*) FROM reels WHERE is_mock = 1").fetchone()[0]
            live_reels = conn.execute("SELECT COUNT(*) FROM reels WHERE is_mock = 0").fetchone()[0]

            ideas_query = "SELECT COUNT(*) FROM adsync_ideas"
            if is_mock is not None:
                ideas_query = """
                    SELECT COUNT(*)
                    FROM adsync_ideas i
                    JOIN reels r ON i.source_reel_id = r.reel_id
                    WHERE r.is_mock = ?
                """
                total_ideas = conn.execute(ideas_query, [1 if is_mock else 0]).fetchone()[0]
            else:
                total_ideas = conn.execute(ideas_query).fetchone()[0]

            # Categorization breakdown
            cat_query = f"""
                SELECT a.primary_category, COUNT(*) as cnt
                FROM reel_analyses a
                JOIN reels r ON a.reel_id = r.reel_id
                {where_analyses}
                GROUP BY a.primary_category
                ORDER BY cnt DESC
            """
            cat_rows = conn.execute(cat_query, params).fetchall()
            cat_breakdown = {r["primary_category"]: r["cnt"] for r in cat_rows}

            relevant_reels = sum(cnt for cat, cnt in cat_breakdown.items() if cat != "Other / Irrelevant")
            irrelevant_reels = cat_breakdown.get("Other / Irrelevant", 0)

            # Content formats breakdown
            fmt_query = f"""
                SELECT a.content_format, COUNT(*) as cnt
                FROM reel_analyses a
                JOIN reels r ON a.reel_id = r.reel_id
                {where_analyses}
                GROUP BY a.content_format
                ORDER BY cnt DESC
            """
            fmt_rows = conn.execute(fmt_query, params).fetchall()
            fmt_breakdown = {r["content_format"]: r["cnt"] for r in fmt_rows}

            # Hook types breakdown
            hook_query = f"""
                SELECT a.hook_type, COUNT(*) as cnt
                FROM reel_analyses a
                JOIN reels r ON a.reel_id = r.reel_id
                {where_analyses}
                GROUP BY a.hook_type
                ORDER BY cnt DESC
            """
            hook_rows = conn.execute(hook_query, params).fetchall()
            hook_breakdown = {r["hook_type"]: r["cnt"] for r in hook_rows}

            # Engagement metrics availability audit
            metrics_query = f"""
                SELECT
                    SUM(CASE WHEN play_count IS NOT NULL THEN 1 ELSE 0 END) as with_plays,
                    SUM(CASE WHEN play_count IS NULL THEN 1 ELSE 0 END) as null_plays,
                    SUM(CASE WHEN like_count IS NOT NULL THEN 1 ELSE 0 END) as with_likes,
                    SUM(CASE WHEN like_count IS NULL THEN 1 ELSE 0 END) as null_likes,
                    SUM(CASE WHEN comment_count IS NOT NULL THEN 1 ELSE 0 END) as with_comments,
                    SUM(CASE WHEN comment_count IS NULL THEN 1 ELSE 0 END) as null_comments,
                    SUM(CASE WHEN share_count IS NOT NULL THEN 1 ELSE 0 END) as with_shares,
                    SUM(CASE WHEN share_count IS NULL THEN 1 ELSE 0 END) as null_shares,
                    SUM(CASE WHEN audio_title IS NOT NULL AND audio_title != '' THEN 1 ELSE 0 END) as with_audio,
                    SUM(CASE WHEN audio_title IS NULL OR audio_title = '' THEN 1 ELSE 0 END) as missing_audio,
                    SUM(CASE WHEN caption IS NOT NULL AND caption != '' THEN 1 ELSE 0 END) as with_caption,
                    SUM(CASE WHEN caption IS NULL OR caption = '' THEN 1 ELSE 0 END) as missing_caption
                FROM reels
                {where_reels}
            """
            m_row = conn.execute(metrics_query, params).fetchone()

            telemetry = {
                "with_plays": m_row["with_plays"] or 0,
                "null_plays": m_row["null_plays"] or 0,
                "with_likes": m_row["with_likes"] or 0,
                "null_likes": m_row["null_likes"] or 0,
                "with_comments": m_row["with_comments"] or 0,
                "null_comments": m_row["null_comments"] or 0,
                "with_shares": m_row["with_shares"] or 0,
                "null_shares": m_row["null_shares"] or 0,
                "with_audio": m_row["with_audio"] or 0,
                "missing_audio": m_row["missing_audio"] or 0,
                "with_caption": m_row["with_caption"] or 0,
                "missing_caption": m_row["missing_caption"] or 0,
            }

            return {
                "total_reels": total_reels,
                "mock_reels": mock_reels,
                "live_reels": live_reels,
                "relevant_reels": relevant_reels,
                "irrelevant_reels": irrelevant_reels,
                "total_ideas": total_ideas,
                "categories": cat_breakdown,
                "formats": fmt_breakdown,
                "hook_types": hook_breakdown,
                "telemetry": telemetry,
            }

    # =========================================================================
    # Competitor Management Persistence
    # =========================================================================

    def save_competitor(self, comp: CompetitorProfile) -> bool:
        """Upserts a competitor profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO competitors (
                handle, category, display_name, bio, avatar_url,
                verified, is_private, follower_count, following_count, posts_count,
                added_at, last_fetched_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                category = excluded.category,
                display_name = coalesce(excluded.display_name, competitors.display_name),
                bio = coalesce(excluded.bio, competitors.bio),
                avatar_url = coalesce(excluded.avatar_url, competitors.avatar_url),
                verified = excluded.verified,
                is_private = excluded.is_private,
                follower_count = coalesce(excluded.follower_count, competitors.follower_count),
                following_count = coalesce(excluded.following_count, competitors.following_count),
                posts_count = coalesce(excluded.posts_count, competitors.posts_count),
                last_fetched_at = coalesce(excluded.last_fetched_at, competitors.last_fetched_at),
                notes = coalesce(excluded.notes, competitors.notes);
            """, (
                comp.handle.strip().lstrip("@").lower(),
                comp.category,
                comp.display_name,
                comp.bio,
                comp.avatar_url,
                1 if comp.verified else 0,
                1 if comp.is_private else 0,
                comp.follower_count,
                comp.following_count,
                comp.posts_count,
                comp.added_at,
                comp.last_fetched_at,
                comp.notes,
            ))
            conn.commit()
            return True

    def get_competitors(self, category: Optional[str] = None) -> List[CompetitorProfile]:
        """Retrieves competitor profiles, optionally filtered by category."""
        query = "SELECT * FROM competitors"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY handle ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            out = []
            for r in rows:
                out.append(CompetitorProfile(
                    handle=r["handle"],
                    category=r["category"],
                    display_name=r["display_name"],
                    bio=r["bio"],
                    avatar_url=r["avatar_url"],
                    verified=bool(r["verified"]),
                    is_private=bool(r["is_private"]),
                    follower_count=r["follower_count"],
                    following_count=r["following_count"],
                    posts_count=r["posts_count"],
                    added_at=r["added_at"],
                    last_fetched_at=r["last_fetched_at"],
                    notes=r["notes"],
                ))
            return out

    def get_competitor(self, handle: str) -> Optional[CompetitorProfile]:
        """Retrieves a single competitor by handle."""
        clean_handle = handle.strip().lstrip("@").lower()
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM competitors WHERE handle = ?", (clean_handle,)).fetchone()
            if not r:
                return None
            return CompetitorProfile(
                handle=r["handle"],
                category=r["category"],
                display_name=r["display_name"],
                bio=r["bio"],
                avatar_url=r["avatar_url"],
                verified=bool(r["verified"]),
                is_private=bool(r["is_private"]),
                follower_count=r["follower_count"],
                following_count=r["following_count"],
                posts_count=r["posts_count"],
                added_at=r["added_at"],
                last_fetched_at=r["last_fetched_at"],
                notes=r["notes"],
            )

    def delete_competitor(self, handle: str) -> bool:
        """Deletes a competitor and cascades deletion of snapshots."""
        clean_handle = handle.strip().lstrip("@").lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM competitor_reel_snapshots WHERE handle = ?", (clean_handle,))
            cursor.execute("DELETE FROM competitors WHERE handle = ?", (clean_handle,))
            conn.commit()
            return cursor.rowcount > 0

    def save_reel_snapshot(self, snapshot: ReelSnapshot) -> bool:
        """Saves a time-series engagement snapshot of a Reel."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO competitor_reel_snapshots (
                snapshot_id, reel_id, handle, captured_at,
                play_count, like_count, comment_count, share_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                snapshot.reel_id,
                snapshot.handle.strip().lstrip("@").lower(),
                snapshot.captured_at,
                snapshot.play_count,
                snapshot.like_count,
                snapshot.comment_count,
                snapshot.share_count,
            ))
            conn.commit()
            return True

    def get_reel_snapshots(self, reel_id: str) -> List[ReelSnapshot]:
        """Retrieves historical snapshots for a Reel in chronological order."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM competitor_reel_snapshots WHERE reel_id = ? ORDER BY captured_at ASC",
                (reel_id,)
            ).fetchall()
            return [
                ReelSnapshot(
                    snapshot_id=r["snapshot_id"],
                    reel_id=r["reel_id"],
                    handle=r["handle"],
                    captured_at=r["captured_at"],
                    play_count=r["play_count"],
                    like_count=r["like_count"],
                    comment_count=r["comment_count"],
                    share_count=r["share_count"],
                )
                for r in rows
            ]

