"""Instagram Graph API Client for Instagram Reels Publishing."""
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from publisher.config import PublisherConfig


class InstagramAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, error_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}


@dataclass
class PublishResult:
    publication_id: str
    status: str
    is_dry_run: bool
    creation_id: Optional[str] = None
    post_id: Optional[str] = None
    permalink: Optional[str] = None
    scheduled_time: Optional[int] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class InstagramPublisher:
    """Handles container creation, status polling, and publishing via Graph API."""

    def __init__(self, config: PublisherConfig):
        self.config = config

    def _mask_token(self, text: str) -> str:
        """Mask credentials to prevent accidental logging."""
        if not self.config.access_token:
            return text
        return text.replace(self.config.access_token, "REDACTED_TOKEN")

    def _http_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute HTTP request using standard library urllib."""
        query_params = params.copy() if params else {}
        query_params["access_token"] = self.config.access_token

        url = f"{self.config.base_url}/{self.config.api_version}/{endpoint.lstrip('/')}"
        encoded_query = urllib.parse.urlencode(query_params)
        full_url = f"{url}?{encoded_query}"

        encoded_data = None
        headers = {"Accept": "application/json"}
        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(full_url, data=encoded_data, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            err_json = {}
            try:
                err_json = json.loads(err_body)
            except Exception:
                pass
            msg = err_json.get("error", {}).get("message", f"HTTP {e.code}: {e.reason}")
            safe_msg = self._mask_token(msg)
            raise InstagramAPIError(safe_msg, status_code=e.code, error_data=err_json)
        except urllib.error.URLError as e:
            safe_reason = self._mask_token(str(e.reason))
            raise InstagramAPIError(f"Network error: {safe_reason}")

    def create_reel_container(
        self,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
        thumb_offset: Optional[int] = None,
        scheduled_publish_time: Optional[int] = None
    ) -> str:
        """Step 1: Create media container for the Reel."""
        endpoint = f"{self.config.instagram_account_id}/media"
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false"
        }
        if thumb_offset is not None:
            payload["thumb_offset"] = str(thumb_offset)
        if scheduled_publish_time is not None:
            payload["scheduled_publish_time"] = str(scheduled_publish_time)

        res = self._http_request("POST", endpoint, data=payload)
        creation_id = res.get("id")
        if not creation_id:
            raise InstagramAPIError("No container ID returned in response", error_data=res)
        return creation_id

    def check_container_status(self, creation_id: str) -> Dict[str, Any]:
        """Step 2: Check processing status of the container."""
        endpoint = creation_id
        params = {"fields": "status_code,status"}
        return self._http_request("GET", endpoint, params=params)

    def publish_container(self, creation_id: str) -> str:
        """Step 3: Publish the ready container."""
        endpoint = f"{self.config.instagram_account_id}/media_publish"
        payload = {"creation_id": creation_id}
        res = self._http_request("POST", endpoint, data=payload)
        post_id = res.get("id")
        if not post_id:
            raise InstagramAPIError("No published post ID returned", error_data=res)
        return post_id

    def get_media_permalink(self, post_id: str) -> Optional[str]:
        """Retrieve the live Instagram permalink for a published post."""
        try:
            endpoint = post_id
            params = {"fields": "permalink"}
            res = self._http_request("GET", endpoint, params=params)
            return res.get("permalink")
        except Exception:
            return None

