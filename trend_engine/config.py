"""Configuration loader and credential protection module for AdSync Trend Engine."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent


def _parse_env_file(env_path: Path) -> dict:
    """Fallback .env parser if python-dotenv is not installed."""
    env_vars = {}
    if not env_path.is_file():
        return env_vars
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    env_vars[k] = v
    except Exception:
        pass
    return env_vars


def load_environment():
    """Loads environment variables from trend_engine/.env or workspace .env."""
    # Attempt python-dotenv first
    try:
        from dotenv import load_dotenv  # type: ignore
        for p in [BASE_DIR / ".env", WORKSPACE_DIR / ".env"]:
            if p.is_file():
                load_dotenv(p)
                return
    except ImportError:
        pass

    # Standard fallback parser
    for p in [BASE_DIR / ".env", WORKSPACE_DIR / ".env"]:
        if p.is_file():
            parsed = _parse_env_file(p)
            for k, v in parsed.items():
                if k not in os.environ:
                    os.environ[k] = v
            break


# Load on import
load_environment()


def mask_key(key: Optional[str]) -> str:
    """Masks sensitive API credentials for safe logging and error reporting."""
    if not key:
        return "<EMPTY>"
    key = str(key).strip()
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}...{key[-4:]}"


@dataclass(frozen=True)
class EngineConfig:
    api_key: str
    base_url: str
    db_path: Path
    force_mock_mode: bool
    fixtures_path: Path

    @property
    def masked_api_key(self) -> str:
        return mask_key(self.api_key)

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-placeholder API key is set."""
        if not self.api_key:
            return False
        placeholders = [
            "your_social_fetch_api_key_here",
            "your_api_key_here",
            "mock_or_pending_subscription_key",
            "placeholder",
        ]
        return self.api_key.lower().strip() not in placeholders


def get_config() -> EngineConfig:
    """Builds and validates the EngineConfig instance."""
    load_environment()
    api_key = os.environ.get("SOCIAL_FETCH_API_KEY", "").strip()
    base_url = os.environ.get("SOCIAL_FETCH_BASE_URL", "https://api.socialfetch.dev").rstrip("/")
    db_env = os.environ.get("TREND_DATABASE_PATH", "trend_engine/data/trends.db").strip()

    db_path = Path(db_env)
    if not db_path.is_absolute():
        db_path = WORKSPACE_DIR / db_path

    force_mock = os.environ.get("FORCE_MOCK_MODE", "1").lower() in ("1", "true", "yes")
    fixtures_path = BASE_DIR / "data" / "fixtures" / "sample_trending_reels.json"

    return EngineConfig(
        api_key=api_key,
        base_url=base_url,
        db_path=db_path,
        force_mock_mode=force_mock,
        fixtures_path=fixtures_path,
    )

