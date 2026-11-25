"""Supabase Storage client for uploading Reels and retrieving public URLs."""
import os
import json
import uuid
import mimetypes
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any


class SupabaseStorageError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, error_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}


class SupabaseStorageClient:
    """Uploads media objects to Supabase Storage buckets via standard library urllib."""

    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str = "adsync-reels"):
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else ""
        self.supabase_key = supabase_key or ""
        self.bucket = bucket_name or "adsync-reels"

    def _mask_key(self, text: str) -> str:
        """Redact supabase key from any exception strings or logs."""
        if not self.supabase_key:
            return text
        return text.replace(self.supabase_key, "REDACTED_SUPABASE_KEY")

    def get_public_url(self, destination_path: str) -> str:
        """Construct the direct public HTTPS URL for a file in a public Supabase bucket."""
        clean_path = destination_path.lstrip("/")
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket}/{clean_path}"

    def upload_file(
        self,
        local_path: str,
        destination_path: Optional[str] = None,
        content_type: Optional[str] = None,
        upsert: bool = True
    ) -> str:
        """
        Upload local file to the configured Supabase bucket and return its public URL.
        Endpoint: POST /storage/v1/object/{bucket}/{destination_path}
        """
        if not self.supabase_url or not self.supabase_key:
            raise SupabaseStorageError("SUPABASE_URL and SUPABASE_KEY must be configured.")

        file_path = Path(local_path)
        if not file_path.is_file():
            raise SupabaseStorageError(f"Local file not found: {local_path}")

        if not destination_path:
            # Use original filename or generate unique name
            destination_path = f"{file_path.name}"

        clean_dest = destination_path.lstrip("/")
        endpoint_url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{clean_dest}"

        if not content_type:
            mime, _ = mimetypes.guess_type(str(file_path))
            content_type = mime or "video/mp4"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        headers = {
            "Authorization": f"Bearer {self.supabase_key}",
            "apikey": self.supabase_key,
            "Content-Type": content_type,
            "x-upsert": "true" if upsert else "false"
        }

        req = urllib.request.Request(endpoint_url, data=file_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_bytes = resp.read()
                try:
                    data = json.loads(resp_bytes.decode("utf-8"))
                except Exception:
                    data = {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            err_json = {}
            try:
                err_json = json.loads(err_body)
            except Exception:
                pass
            msg = err_json.get("message") or err_json.get("error") or f"HTTP {e.code}: {e.reason}"
            safe_msg = self._mask_key(msg)
            raise SupabaseStorageError(f"Supabase upload failed: {safe_msg}", status_code=e.code, error_data=err_json)
        except urllib.error.URLError as e:
            safe_reason = self._mask_key(str(e.reason))
            raise SupabaseStorageError(f"Supabase network error: {safe_reason}")

        return self.get_public_url(clean_dest)

    def verify_public_url(self, public_url: str, timeout: int = 15) -> bool:
        """Verify the public URL is reachable with HTTP 200 via HEAD/GET request."""
        req = urllib.request.Request(public_url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in (200, 206)
        except urllib.error.HTTPError:
            # Some CDNs or storage engines reject HEAD requests; fallback to GET with Range 0-1
            try:
                get_req = urllib.request.Request(public_url, headers={"Range": "bytes=0-1"}, method="GET")
                with urllib.request.urlopen(get_req, timeout=timeout) as resp:
                    return resp.status in (200, 206)
            except Exception:
                return False
        except Exception:
            return False

