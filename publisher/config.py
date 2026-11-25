"""Configuration and credential management for Instagram Graph API Publisher."""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def load_env(env_path: Optional[Path] = None):
    """Load environment variables from .env file without external dependencies."""
    if env_path is None:
        # Check current working directory, then publisher directory, then trend_engine
        candidates = [
            Path.cwd() / ".env",
            Path(__file__).resolve().parent / ".env",
            Path(__file__).resolve().parent.parent / ".env",
            Path(__file__).resolve().parent.parent / "trend_engine" / ".env"
        ]
        for c in candidates:
            if c.is_file():
                env_path = c
                break

    if env_path and env_path.is_file():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


@dataclass
class PublisherConfig:
    access_token: str
    instagram_account_id: str
    api_version: str = "v21.0"
    base_url: str = "https://graph.facebook.com"
    dry_run: bool = True
    db_path: Path = Path("trend_engine/data/trends.db")
    video_host_base_url: Optional[str] = None
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_bucket: str = "adsync-reels"

    @classmethod
    def from_env(cls) -> "PublisherConfig":
        load_env()
        token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
        account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "").strip()
        api_ver = os.environ.get("INSTAGRAM_GRAPH_API_VERSION", "v21.0").strip()
        dry_run_env = os.environ.get("INSTAGRAM_DRY_RUN", "1").strip().lower()
        dry_run = dry_run_env in ("1", "true", "yes", "on")
        # Default db path relative to project root
        project_root = Path(__file__).resolve().parent.parent
        default_db = project_root / "trend_engine" / "data" / "trends.db"
        db_path_str = os.environ.get("TREND_DATABASE_PATH", "").strip()
        db_path = Path(db_path_str) if db_path_str else default_db
        if not db_path.is_absolute():
            db_path = project_root / db_path
        host_url = os.environ.get("VIDEO_HOST_BASE_URL", "").strip() or None
        sb_url = os.environ.get("SUPABASE_URL", "").strip()
        sb_key = os.environ.get("SUPABASE_KEY", "").strip()
        sb_bucket = os.environ.get("SUPABASE_BUCKET", "adsync-reels").strip() or "adsync-reels"

        return cls(
            access_token=token,
            instagram_account_id=account_id,
            api_version=api_ver,
            dry_run=dry_run,
            db_path=db_path,
            video_host_base_url=host_url,
            supabase_url=sb_url,
            supabase_key=sb_key,
            supabase_bucket=sb_bucket
        )
