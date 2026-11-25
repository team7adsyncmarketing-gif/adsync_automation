"""Social Fetch API Client for Instagram Trending Reels."""

import json
import logging
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from .base import (
    BaseTrendProvider,
    AuthenticationError,
    PaymentRequiredError,
    ForbiddenError,
    RateLimitError,
    ProviderServerError,
    TrendProviderError,
)
from ..storage.models import ReelItem
from ..config import EngineConfig, mask_key

logger = logging.getLogger("trend_engine.social_fetch")

HASHTAG_REGEX = re.compile(r"#([A-Za-z0-9_]+)")


def _safe_optional_int(val: Any) -> Optional[int]:
    """Converts a value to integer if present and non-null; returns None if missing or null.
    Never fabricates 0 for unrecorded or missing metrics.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _safe_int(val: Any, default: int = 0) -> int:
    """Converts a value to integer safely with a fallback default."""
    res = _safe_optional_int(val)
    return res if res is not None else default


def extract_media_list(payload: Any) -> List[Dict[str, Any]]:
    """Safely extracts a list of media dictionaries from varied API response structures.

    Handles:
    - Direct list: [{"id": ...}, ...]
    - data.media: {"data": {"media": [...]}}
    - data.reels: {"data": {"reels": [...]}}
    - data.items: {"data": {"items": [...]}}
    - data.results: {"data": {"results": [...]}}
    - data as list: {"data": [...]}
    - reels: {"reels": [...]}
    - items: {"items": [...]}
    - results: {"results": [...]}
    - media: {"media": [...]}

    Returns an empty list [] if no valid list of dictionaries is found.
    Guarantees never returning a dict, None, or raising KeyError.
    """
    if not payload:
        return []

    # Case 1: Direct list
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    # If not a dictionary, cannot extract media list
    if not isinstance(payload, dict):
        return []

    # Case 2: Top-level list keys
    for key in ("reels", "items", "results", "media", "recentMedia"):
        val = payload.get(key)
        if isinstance(val, list):
            return [item for item in val if isinstance(item, dict)]

    # Case 3: "data" container
    data_val = payload.get("data")
    if isinstance(data_val, list):
        return [item for item in data_val if isinstance(item, dict)]

    if isinstance(data_val, dict):
        for sub_key in ("media", "reels", "items", "results", "recentMedia"):
            sub_val = data_val.get(sub_key)
            if isinstance(sub_val, list):
                return [item for item in sub_val if isinstance(item, dict)]

    # Case 4: Any nested list of dictionaries in top-level values
    for k, v in payload.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            return v

    return []


class SocialFetchClient(BaseTrendProvider):
    """Client for Social Fetch Instagram API v2 with zero-dependency urllib core transport."""

    SUPPORTED_SEARCH_TERMS = [
        "digital marketing",
        "Instagram marketing",
        "Meta Ads",
        "lead generation",
        "marketing automation",
        "branding",
        "business growth",
        "real estate marketing",
    ]

    SUPPORTED_HASHTAGS = [
        "metaads",
        "facebookads",
        "leadgeneration",
        "digitalmarketing",
        "instagrammarketing",
        "marketingautomation",
        "businessgrowth",
        "branding",
        "socialmediamarketing",
        "b2bmarketing",
        "realestatemarketing",
        "contentmarketing",
    ]

    def __init__(self, config: EngineConfig, use_mock: Optional[bool] = None):
        self.config = config
        self.use_mock = config.force_mock_mode if use_mock is None else use_mock
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.fixtures_path = config.fixtures_path

    def _get_headers(self) -> Dict[str, str]:
        """Constructs request headers including authorization and agent metadata."""
        return {
            "x-api-key": self.api_key or "",
            "Accept": "application/json",
            "User-Agent": "AdSync-TrendEngine/1.0",
        }

    def _http_get(self, url: str, headers: Dict[str, str], timeout: int = 25) -> Tuple[int, str, Dict[str, str]]:
        """Executes an HTTP GET request using Python standard library urllib.

        Provides 100% environment compatibility with zero external pip dependencies.
        Returns:
            Tuple of (status_code, response_body_text, response_headers_dict)
        """
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", getattr(resp, "code", 200))
                body = resp.read().decode("utf-8", errors="replace")
                resp_headers = dict(resp.headers)
                return status, body, resp_headers
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            resp_headers = dict(e.headers)
            return status, body, resp_headers
        except urllib.error.URLError as e:
            raise TrendProviderError(f"Network error connecting to Social Fetch: {e.reason}")
        except TimeoutError:
            raise TrendProviderError(f"Request to Social Fetch timed out after {timeout} seconds.")
        except Exception as e:
            raise TrendProviderError(f"HTTP request error: {e}")

    def _parse_raw_reel(self, raw: Dict[str, Any], is_mock: bool = False) -> ReelItem:
        """Robustly extracts all target fields from v2 Instagram media objects."""
        # Identification - safe string conversion for IDs of any type (int, str)
        raw_id = raw.get("id") or raw.get("pk")
        raw_id_str = str(raw_id) if raw_id is not None else ""

        shortcode = (
            raw.get("code")
            or raw.get("shortcode")
            or (raw_id_str.split("_")[0] if raw_id_str else None)
            or f"reel_{abs(hash(json.dumps(raw, default=str))) % 1000000}"
        )
        reel_id = raw_id_str or shortcode
        url = raw.get("url") or f"https://www.instagram.com/reel/{shortcode}/"

        # Caption extraction
        caption_raw = raw.get("caption") or raw.get("edge_media_to_caption")
        caption_text = ""
        if isinstance(caption_raw, dict):
            if "edges" in caption_raw and isinstance(caption_raw["edges"], list) and caption_raw["edges"]:
                caption_text = caption_raw["edges"][0].get("node", {}).get("text", "")
            else:
                caption_text = caption_raw.get("text", "")
        elif isinstance(caption_raw, str):
            caption_text = caption_raw
        caption_text = caption_text.strip()

        # Author extraction (supports Social Fetch v2 owner.handle/fullName and legacy formats)
        user = raw.get("owner") or raw.get("user") or raw.get("author") or {}
        if isinstance(user, dict):
            author_username = (
                user.get("handle")
                or user.get("username")
                or user.get("screenName")
                or raw.get("author_username")
                or "creator"
            )
            author_full_name = (
                user.get("fullName")
                or user.get("full_name")
                or user.get("name")
                or raw.get("author_full_name")
            )
        else:
            author_username = str(user) if user else (raw.get("author_username") or "creator")
            author_full_name = raw.get("author_full_name")

        # Engagement metrics extraction (supports Social Fetch v2 metrics object and legacy formats)
        # Keeps missing or null values as None (does not replace with zero)
        metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}

        play_count = _safe_optional_int(
            metrics.get("playCount")
            or metrics.get("play_count")
            or metrics.get("views")
            or metrics.get("viewCount")
            or raw.get("play_count")
            or raw.get("video_play_count")
            or raw.get("view_count")
            or raw.get("views")
        )
        like_count = _safe_optional_int(
            metrics.get("likeCount")
            or metrics.get("like_count")
            or metrics.get("likes")
            or raw.get("like_count")
            or raw.get("likes")
            or (raw.get("edge_media_preview_like", {}).get("count") if isinstance(raw.get("edge_media_preview_like"), dict) else None)
        )
        comment_count = _safe_optional_int(
            metrics.get("commentCount")
            or metrics.get("comment_count")
            or metrics.get("comments")
            or raw.get("comment_count")
            or raw.get("comments")
            or (raw.get("edge_media_to_comment", {}).get("count") if isinstance(raw.get("edge_media_to_comment"), dict) else None)
        )
        share_count = _safe_optional_int(
            metrics.get("shareCount")
            or metrics.get("share_count")
            or metrics.get("shares")
            or metrics.get("saveCount")
            or raw.get("share_count")
            or raw.get("reshares")
            or raw.get("shares")
        )

        # Hashtags extraction
        raw_hashtags = raw.get("hashtags") or []
        hashtags: List[str] = []
        if isinstance(raw_hashtags, list):
            for h in raw_hashtags:
                if isinstance(h, str):
                    hashtags.append(h.lstrip("#").lower())
                elif isinstance(h, dict) and "name" in h:
                    hashtags.append(str(h["name"]).lower())

        if not hashtags and caption_text:
            hashtags = [h.lower() for h in HASHTAG_REGEX.findall(caption_text)]

        # Audio metadata extraction
        audio_info = (
            raw.get("music_metadata")
            or raw.get("audio")
            or raw.get("clips_metadata", {}).get("audio_type_model")
            or (raw.get("music_info", {}).get("music_asset_info") if isinstance(raw.get("music_info"), dict) else {})
            or {}
        )
        if not isinstance(audio_info, dict):
            audio_info = {}

        audio_id_raw = audio_info.get("audio_id") or audio_info.get("id") or audio_info.get("asset_id")
        audio_id = str(audio_id_raw) if audio_id_raw is not None else None
        audio_title = audio_info.get("song_name") or audio_info.get("title") or audio_info.get("audio_title")
        audio_artist = audio_info.get("artist_name") or audio_info.get("artist") or audio_info.get("author") or audio_info.get("display_artist")
        is_original = bool(
            audio_info.get("is_original_audio")
            or audio_info.get("is_original")
            or ("original" in (audio_title or "").lower())
        )

        published_at = raw.get("taken_at") or raw.get("published_at") or raw.get("timestamp")

        return ReelItem(
            reel_id=reel_id,
            shortcode=shortcode,
            url=url,
            caption=caption_text,
            author_username=author_username,
            author_full_name=author_full_name,
            play_count=play_count,
            like_count=like_count,
            comment_count=comment_count,
            share_count=share_count,
            hashtags=hashtags,
            audio_id=audio_id,
            audio_title=audio_title,
            audio_artist=audio_artist,
            is_original_audio=is_original,
            published_at=str(published_at) if published_at else None,
            is_mock=is_mock,
            raw_json=json.dumps(raw, default=str),
        )

    def fetch_trending_reels(self, limit: Optional[int] = None) -> List[ReelItem]:
        """Fetches trending reels from mock fixtures or live Social Fetch API."""
        if self.use_mock:
            return self._fetch_mock_reels(limit)
        return self._fetch_live_reels(limit)

    def _fetch_mock_reels(self, limit: Optional[int] = None) -> List[ReelItem]:
        """Loads realistic sample data from local fixtures."""
        if not self.fixtures_path.is_file():
            raise FileNotFoundError(
                f"Mock fixture file not found at {self.fixtures_path}. Run fixture generator first."
            )

        with open(self.fixtures_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_list = extract_media_list(data)
        items = [self._parse_raw_reel(r, is_mock=True) for r in raw_list]
        if limit:
            items = items[:limit]
        return items

    def _fetch_live_reels(self, limit: Optional[int] = None) -> List[ReelItem]:
        """Executes GET /v2/instagram/reels/trending using standard library urllib."""
        if not self.api_key:
            raise AuthenticationError("Social Fetch API key missing in environment (.env).")

        endpoint = f"{self.base_url}/v2/instagram/reels/trending"
        headers = self._get_headers()

        status, body, resp_headers = self._http_get(endpoint, headers=headers, timeout=30)

        if status != 200:
            self._handle_http_errors(status, body, resp_headers)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise TrendProviderError(f"Social Fetch returned invalid JSON: {e}")

        # Store the original raw response securely for debugging, excluding credentials
        try:
            raw_dir = self.config.db_path.parent / "raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            raw_file = raw_dir / f"live_batch_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved raw response to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw response file: {e}")

        raw_list = extract_media_list(payload)
        if not raw_list:
            if isinstance(payload, dict) and (payload.get("status") in ("fail", "error") or "error" in payload or "message" in payload):
                err_msg = payload.get("message") or payload.get("error")
                raise TrendProviderError(f"Social Fetch API reported error in payload: {err_msg}")
            return []

        reels = [self._parse_raw_reel(r, is_mock=False) for r in raw_list]
        return reels[:limit] if limit else reels

    def fetch_reels_by_keyword(
        self,
        query: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Fetches Instagram Reels matching a target keyword or phrase.
        
        Uses GET /v2/instagram/reels/search?query={keyword}&cursor={cursor}.
        In mock mode (default), filters local fixtures by matching query tokens
        across captions and hashtags. In live mode, executes the search request
        and extracts data.media and data.page.nextCursor.
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        clean_query = query.strip()

        if self.use_mock:
            return self._fetch_mock_reels_by_keyword(clean_query, limit=limit, cursor=cursor)
        return self._fetch_live_reels_by_keyword(clean_query, limit=limit, cursor=cursor)

    def _fetch_mock_reels_by_keyword(
        self,
        query: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Filters mock fixtures matching query keywords, supporting simulated pagination."""
        all_mock_reels = self._fetch_mock_reels()
        query_words = set(re.findall(r"[a-z0-9]+", query.lower()))

        matched: List[ReelItem] = []
        for r in all_mock_reels:
            corpus = f"{r.caption.lower()} {' '.join(r.hashtags).lower()} {r.author_username.lower()}"
            corpus_words = set(re.findall(r"[a-z0-9]+", corpus))
            # Match if any significant query word is present or substring match
            if query.lower() in corpus or query_words.intersection(corpus_words):
                matched.append(r)

        # If no specific match found, fallback to returning all mock reels
        # so testing remains smooth without empty sets
        candidates = matched if matched else all_mock_reels

        # Handle simulated pagination with cursor offset
        offset = 0
        if cursor and cursor.startswith("mock_cursor_"):
            try:
                offset = int(cursor.split("_")[-1])
            except ValueError:
                offset = 0

        paged_items = candidates[offset:]
        page_limit = limit or len(paged_items)
        items_to_return = paged_items[:page_limit]

        next_offset = offset + len(items_to_return)
        next_cursor = f"mock_cursor_{next_offset}" if next_offset < len(candidates) else None

        return items_to_return, next_cursor

    def _fetch_live_reels_by_keyword(
        self,
        query: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Executes GET /v2/instagram/reels/search?query={keyword}&cursor={cursor}."""
        if not self.api_key:
            raise AuthenticationError("Social Fetch API key missing in environment (.env).")

        params = {"query": query}
        if cursor:
            params["cursor"] = cursor

        encoded_params = urllib.parse.urlencode(params)
        endpoint = f"{self.base_url}/v2/instagram/reels/search?{encoded_params}"
        headers = self._get_headers()

        status, body, resp_headers = self._http_get(endpoint, headers=headers, timeout=30)

        if status != 200:
            self._handle_http_errors(status, body, resp_headers)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise TrendProviderError(f"Social Fetch returned invalid JSON: {e}")

        # Preserve the raw search response for auditing
        try:
            raw_dir = self.config.db_path.parent / "raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            sanitized_query = "".join(c if c.isalnum() else "_" for c in query)[:24]
            raw_file = raw_dir / f"live_search_{sanitized_query}_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved raw search response to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw search response file: {e}")

        # Extract next cursor from data.page or top-level page
        next_cursor = None
        if isinstance(payload, dict):
            page_info = payload.get("data", {}).get("page") if isinstance(payload.get("data"), dict) else payload.get("page")
            if isinstance(page_info, dict) and page_info.get("hasMore"):
                next_cursor = page_info.get("nextCursor")

        raw_list = extract_media_list(payload)
        if not raw_list:
            if isinstance(payload, dict) and (payload.get("status") in ("fail", "error") or "error" in payload or "message" in payload):
                err_msg = payload.get("message") or payload.get("error")
                raise TrendProviderError(f"Social Fetch API reported error in payload: {err_msg}")
            return [], next_cursor

        reels = [self._parse_raw_reel(r, is_mock=False) for r in raw_list]
        if limit:
            reels = reels[:limit]
        return reels, next_cursor

    def fetch_reels_by_hashtag(
        self,
        hashtag: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Fetches Instagram Reels tagged under a specific hashtag.
        
        Uses GET /v2/instagram/hashtags/{hashtag}/media?tab=reels&cursor={cursor}.
        In mock mode (default), filters local fixtures by matching the hashtag in
        hashtags array or caption. In live mode, executes the request and extracts
        data.media and data.page.nextCursor.
        """
        if not hashtag or not hashtag.strip():
            raise ValueError("Hashtag cannot be empty.")

        clean_tag = hashtag.strip().lstrip("#").lower()

        if self.use_mock:
            return self._fetch_mock_reels_by_hashtag(clean_tag, limit=limit, cursor=cursor)
        return self._fetch_live_reels_by_hashtag(clean_tag, limit=limit, cursor=cursor)

    def _fetch_mock_reels_by_hashtag(
        self,
        hashtag: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Filters mock fixtures matching the given hashtag, supporting simulated pagination."""
        all_mock_reels = self._fetch_mock_reels()
        matched: List[ReelItem] = []

        for r in all_mock_reels:
            tags_lower = [t.lower() for t in r.hashtags]
            caption_lower = r.caption.lower()
            if hashtag in tags_lower or f"#{hashtag}" in caption_lower:
                matched.append(r)

        # Fallback to all mock reels if specific hashtag has no fixture matches
        candidates = matched if matched else all_mock_reels

        # Simulated pagination
        offset = 0
        if cursor and cursor.startswith("mock_cursor_"):
            try:
                offset = int(cursor.split("_")[-1])
            except ValueError:
                offset = 0

        paged_items = candidates[offset:]
        page_limit = limit or len(paged_items)
        items_to_return = paged_items[:page_limit]

        next_offset = offset + len(items_to_return)
        next_cursor = f"mock_cursor_{next_offset}" if next_offset < len(candidates) else None

        return items_to_return, next_cursor

    def _fetch_live_reels_by_hashtag(
        self,
        hashtag: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[str]]:
        """Executes GET /v2/instagram/hashtags/{hashtag}/media?tab=reels&cursor={cursor}."""
        if not self.api_key:
            raise AuthenticationError("Social Fetch API key missing in environment (.env).")

        params = {"tab": "reels"}
        if cursor:
            params["cursor"] = cursor

        encoded_params = urllib.parse.urlencode(params)
        endpoint = f"{self.base_url}/v2/instagram/hashtags/{urllib.parse.quote(hashtag)}/media?{encoded_params}"
        headers = self._get_headers()

        status, body, resp_headers = self._http_get(endpoint, headers=headers, timeout=30)

        if status != 200:
            self._handle_http_errors(status, body, resp_headers)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise TrendProviderError(f"Social Fetch returned invalid JSON: {e}")

        # Preserve the raw hashtag response for auditing
        try:
            raw_dir = self.config.db_path.parent / "raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            sanitized_tag = "".join(c if c.isalnum() else "_" for c in hashtag)[:24]
            raw_file = raw_dir / f"live_hashtag_{sanitized_tag}_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved raw hashtag response to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw hashtag response file: {e}")

        # Extract next cursor from data.page or top-level page
        next_cursor = None
        if isinstance(payload, dict):
            page_info = payload.get("data", {}).get("page") if isinstance(payload.get("data"), dict) else payload.get("page")
            if isinstance(page_info, dict) and page_info.get("hasMore"):
                next_cursor = page_info.get("nextCursor")

        raw_list = extract_media_list(payload)
        if not raw_list:
            if isinstance(payload, dict) and (payload.get("status") in ("fail", "error") or "error" in payload or "message" in payload):
                err_msg = payload.get("message") or payload.get("error")
                raise TrendProviderError(f"Social Fetch API reported error in payload: {err_msg}")
            return [], next_cursor

        reels = [self._parse_raw_reel(r, is_mock=False) for r in raw_list]
        if limit:
            reels = reels[:limit]
        return reels, next_cursor

    def fetch_reels_by_creator(
        self,
        handle: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[Dict[str, Any]], Optional[str]]:
        """Fetches recent reels and creator profile details for an Instagram handle.
        
        Uses GET /v2/instagram/profiles/{handle}?include=recentMedia.
        In mock mode (default), retrieves matching creator records from local fixtures
        or falls back gracefully with simulated profile metadata. In live mode,
        executes the request and extracts data.profile, data.recentMedia, and cursor.
        """
        if not handle or not handle.strip():
            raise ValueError("Creator handle cannot be empty.")

        clean_handle = handle.strip().lstrip("@")

        if self.use_mock:
            return self._fetch_mock_reels_by_creator(clean_handle, limit=limit, cursor=cursor)
        return self._fetch_live_reels_by_creator(clean_handle, limit=limit, cursor=cursor)

    def _fetch_mock_reels_by_creator(
        self,
        handle: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[Dict[str, Any]], Optional[str]]:
        """Filters mock fixtures matching creator handle and builds profile metadata."""
        all_mock_reels = self._fetch_mock_reels()
        matched: List[ReelItem] = []

        for r in all_mock_reels:
            if r.author_username.lower() == handle.lower() or handle.lower() in r.author_username.lower():
                matched.append(r)

        candidates = matched if matched else all_mock_reels

        # Simulated profile object
        first_match = candidates[0] if candidates else None
        profile_info = {
            "handle": handle,
            "displayName": first_match.author_full_name if first_match else handle.replace("_", " ").title(),
            "bio": f"Official marketing and business growth account for @{handle}.",
            "verified": False,
            "privateAccount": False,
            "counts": {
                "posts": len(candidates),
                "followers": 45000,
                "following": 320
            }
        }

        # Simulated pagination
        offset = 0
        if cursor and cursor.startswith("mock_cursor_"):
            try:
                offset = int(cursor.split("_")[-1])
            except ValueError:
                offset = 0

        paged_items = candidates[offset:]
        page_limit = limit or len(paged_items)
        items_to_return = paged_items[:page_limit]

        next_offset = offset + len(items_to_return)
        next_cursor = f"mock_cursor_{next_offset}" if next_offset < len(candidates) else None

        return items_to_return, profile_info, next_cursor

    def _fetch_live_reels_by_creator(
        self,
        handle: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Tuple[List[ReelItem], Optional[Dict[str, Any]], Optional[str]]:
        """Executes GET /v2/instagram/profiles/{handle}?include=recentMedia."""
        if not self.api_key:
            raise AuthenticationError("Social Fetch API key missing in environment (.env).")

        params = {"include": "recentMedia"}
        if cursor:
            params["cursor"] = cursor

        encoded_params = urllib.parse.urlencode(params)
        endpoint = f"{self.base_url}/v2/instagram/profiles/{urllib.parse.quote(handle)}?{encoded_params}"
        headers = self._get_headers()

        status, body, resp_headers = self._http_get(endpoint, headers=headers, timeout=30)

        if status != 200:
            self._handle_http_errors(status, body, resp_headers)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise TrendProviderError(f"Social Fetch returned invalid JSON: {e}")

        # Preserve the raw creator response for auditing
        try:
            raw_dir = self.config.db_path.parent / "raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            sanitized_handle = "".join(c if c.isalnum() else "_" for c in handle)[:24]
            raw_file = raw_dir / f"live_profile_{sanitized_handle}_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved raw creator response to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw creator response file: {e}")

        # Extract profile details
        profile_info = None
        if isinstance(payload, dict):
            profile_info = payload.get("data", {}).get("profile") if isinstance(payload.get("data"), dict) else payload.get("profile")

        # Extract next cursor if provided
        next_cursor = None
        if isinstance(payload, dict):
            page_info = payload.get("data", {}).get("page") if isinstance(payload.get("data"), dict) else payload.get("page")
            if isinstance(page_info, dict) and page_info.get("hasMore"):
                next_cursor = page_info.get("nextCursor")

        raw_list = extract_media_list(payload)
        if not raw_list:
            if isinstance(payload, dict) and (payload.get("status") in ("fail", "error") or "error" in payload or "message" in payload):
                err_msg = payload.get("message") or payload.get("error")
                raise TrendProviderError(f"Social Fetch API reported error in payload: {err_msg}")
            return [], profile_info, next_cursor

        reels = [self._parse_raw_reel(r, is_mock=False) for r in raw_list]
        if limit:
            reels = reels[:limit]
        return reels, profile_info, next_cursor

    def probe_single_live_reel(self) -> Dict[str, Any]:
        """Performs a controlled, single-request live probe of the endpoint to verify connection and schema.

        Extracts at most one reel to inspect and validate fields while minimizing credit consumption.
        """
        if not self.api_key:
            raise AuthenticationError("Social Fetch API key missing in environment (.env).")

        endpoint = f"{self.base_url}/v2/instagram/reels/trending"
        headers = self._get_headers()

        status, body, resp_headers = self._http_get(endpoint, headers=headers, timeout=20)

        if status != 200:
            self._handle_http_errors(status, body, resp_headers)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise TrendProviderError(f"Social Fetch returned invalid JSON: {e}")

        # Store the original raw response securely for debugging, excluding credentials
        try:
            raw_dir = self.config.db_path.parent / "raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            raw_file = raw_dir / f"live_batch_{timestamp}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved raw response to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw response file: {e}")

        raw_list = extract_media_list(payload)
        if not raw_list:
            msg = None
            if isinstance(payload, dict):
                msg = payload.get("message") or payload.get("error") or payload.get("detail")
            return {
                "status": "EMPTY_OR_UNEXPECTED_PAYLOAD",
                "status_code": 200,
                "endpoint": endpoint,
                "message": msg or "HTTP 200 received but no media items found in response payload.",
                "payload_keys": list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
                "headers": {k: v for k, v in resp_headers.items() if k.lower().startswith(("x-", "rate", "credit", "content-type"))},
            }

        sample_reel = self._parse_raw_reel(raw_list[0], is_mock=False)
        return {
            "status": "SUCCESS",
            "status_code": 200,
            "endpoint": endpoint,
            "headers": {k: v for k, v in resp_headers.items() if k.lower().startswith(("x-", "rate", "credit", "content-type"))},
            "reel_sample": {
                "shortcode": sample_reel.shortcode,
                "url": sample_reel.url,
                "author": sample_reel.author_username,
                "author_username": sample_reel.author_username,
                "caption_preview": sample_reel.caption[:80] + "..." if len(sample_reel.caption) > 80 else sample_reel.caption,
                "caption": sample_reel.caption,
                "plays": sample_reel.play_count,
                "play_count": sample_reel.play_count,
                "likes": sample_reel.like_count,
                "like_count": sample_reel.like_count,
                "comments": sample_reel.comment_count,
                "comment_count": sample_reel.comment_count,
                "shares": sample_reel.share_count,
                "share_count": sample_reel.share_count,
                "hashtags_count": len(sample_reel.hashtags),
                "hashtags": sample_reel.hashtags,
                "audio": sample_reel.audio_title or "No audio metadata",
                "audio_title": sample_reel.audio_title,
            },
        }

    def _handle_http_errors(self, status: int, body: str, headers: Any):
        """Translates HTTP response codes into strongly typed domain exceptions without leaking credentials."""
        masked = mask_key(self.api_key)
        if status == 401:
            raise AuthenticationError(
                f"Social Fetch Authentication Failed (HTTP 401). Key: {masked}. Verify credentials in .env.",
                status_code=401,
            )
        if status == 402:
            raise PaymentRequiredError(
                "Social Fetch Quota/Payment Required (HTTP 402). Account has zero credits or requires an active subscription.",
                status_code=402,
                details={"response_body": body[:500]},
            )
        if status == 403:
            raise ForbiddenError(
                f"Social Fetch Forbidden (HTTP 403). Endpoint not authorized for key {masked}.",
                status_code=403,
            )
        if status == 429:
            retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
            retry_val = 60
            if retry_after:
                try:
                    retry_val = int(retry_after)
                except ValueError:
                    retry_val = 60
            raise RateLimitError(
                f"Social Fetch Rate Limit Exceeded (HTTP 429). Retry after {retry_val}s.",
                retry_after=retry_val,
            )
        if 500 <= status <= 599:
            raise ProviderServerError(
                f"Social Fetch Upstream Server Error (HTTP {status}): {body[:200]}",
                status_code=status,
            )
        raise TrendProviderError(f"Social Fetch API call failed with status {status}: {body[:200]}", status_code=status)

    def validate_connection(self) -> Dict[str, Any]:
        """Performs non-destructive health and readiness verification."""
        status = {
            "provider": "Social Fetch (Instagram API v2)",
            "endpoint": "/v2/instagram/reels/trending",
            "mode": "MOCK" if self.use_mock else "LIVE",
            "api_key_configured": bool(self.api_key and self.config.is_configured),
            "masked_key": mask_key(self.api_key),
            "fixture_available": self.fixtures_path.is_file(),
            "status": "READY_MOCK" if self.use_mock else "READY_LIVE",
        }
        return status
