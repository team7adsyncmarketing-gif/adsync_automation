"""Official YouTube Data API v3 integration with safe test / dry-run mode."""
import os
import json
import uuid
import mimetypes
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List


class YouTubeAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, error_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}


@dataclass
class YouTubePublishResult:
    publication_id: str
    status: str
    is_dry_run: bool
    video_id: Optional[str] = None
    permalink: Optional[str] = None
    scheduled_time: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class YouTubePublisher:
    """Uploads videos via the official YouTube Data API v3 (videos.insert)."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        dry_run: bool = True
    ):
        self.access_token = access_token or os.environ.get("YOUTUBE_ACCESS_TOKEN", "").strip()
        self.dry_run = dry_run

    def _mask_token(self, text: str) -> str:
        if not self.access_token:
            return text
        return text.replace(self.access_token, "REDACTED_YOUTUBE_TOKEN")

    def publish_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "public",  # public, unlisted, private
        scheduled_publish_time: Optional[str] = None,  # ISO 8601 string: 2026-11-25T15:00:00Z
        dry_run: Optional[bool] = None
    ) -> YouTubePublishResult:
        is_dry_run = dry_run if dry_run is not None else self.dry_run
        vpath = Path(video_path)
        pub_id = f"yt_{uuid.uuid4().hex[:12]}"
        tags = tags or []

        if not vpath.is_file():
            return YouTubePublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=is_dry_run,
                error_message=f"Video file not found: {video_path}"
            )

        # Dry-run execution path
        if is_dry_run:
            mock_video_id = f"yt_{uuid.uuid4().hex[:11]}"
            status = "SCHEDULED" if scheduled_publish_time else "DRY_RUN"
            permalink = f"https://www.youtube.com/shorts/{mock_video_id}"
            return YouTubePublishResult(
                publication_id=pub_id,
                status=status,
                is_dry_run=True,
                video_id=mock_video_id,
                permalink=permalink,
                scheduled_time=scheduled_publish_time,
                raw_response={
                    "mode": "dry_run",
                    "title": title,
                    "tags": tags,
                    "privacy": privacy_status,
                    "simulated_video_id": mock_video_id
                }
            )

        # Live YouTube Upload Execution Path
        if not self.access_token:
            return YouTubePublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message="Live YouTube upload requires YOUTUBE_ACCESS_TOKEN in environment."
            )

        # YouTube Data API Resumable Upload
        # 1. Initiate Resumable Upload Session
        snippet = {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "22"  # People & Blogs / Marketing
        }
        status_dict: Dict[str, Any] = {"privacyStatus": privacy_status}
        if scheduled_publish_time:
            status_dict["publishAt"] = scheduled_publish_time
            status_dict["privacyStatus"] = "private"  # YouTube requires private when scheduled

        metadata = {
            "snippet": snippet,
            "status": status_dict
        }

        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        metadata_bytes = json.dumps(metadata).encode("utf-8")
        file_size = vpath.stat().st_size

        init_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size)
        }

        req = urllib.request.Request(init_url, data=metadata_bytes, headers=init_headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                upload_url = resp.headers.get("Location")
                if not upload_url:
                    raise YouTubeAPIError("YouTube did not return a resumable upload Location header.")

            # 2. Upload Video Binary
            with open(vpath, "rb") as vf:
                video_bytes = vf.read()

            upload_headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size)
            }

            up_req = urllib.request.Request(upload_url, data=video_bytes, headers=upload_headers, method="PUT")
            with urllib.request.urlopen(up_req, timeout=300) as up_resp:
                result_json = json.loads(up_resp.read().decode("utf-8"))

            video_id = result_json.get("id")
            if not video_id:
                raise YouTubeAPIError("Upload succeeded but no video ID was returned.", error_data=result_json)

            permalink = f"https://www.youtube.com/shorts/{video_id}"
            final_status = "SCHEDULED" if scheduled_publish_time else "PUBLISHED"

            return YouTubePublishResult(
                publication_id=pub_id,
                status=final_status,
                is_dry_run=False,
                video_id=video_id,
                permalink=permalink,
                scheduled_time=scheduled_publish_time,
                raw_response=result_json
            )

        except urllib.error.HTTPError as e:
            err_raw = e.read().decode("utf-8", errors="replace")
            try:
                err_data = json.loads(err_raw)
                err_msg = err_data.get("error", {}).get("message", f"HTTP {e.code}: {e.reason}")
            except Exception:
                err_data = {}
                err_msg = f"HTTP {e.code}: {e.reason}"
            safe_msg = self._mask_token(err_msg)
            return YouTubePublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=safe_msg,
                raw_response=err_data
            )
        except Exception as e:
            return YouTubePublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=self._mask_token(str(e))
            )
