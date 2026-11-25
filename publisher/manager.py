"""High-level Orchestrator for Instagram Reels Publishing."""
import uuid
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from publisher.config import PublisherConfig
from publisher.storage import PublisherDatabase
from publisher.client import InstagramPublisher, PublishResult, InstagramAPIError
from publisher.supabase_uploader import SupabaseStorageClient, SupabaseStorageError


class ReelPublishManager:
    """Orchestrates video validation, caption formatting, dry-run checks, and publishing."""

    def __init__(self, config: Optional[PublisherConfig] = None):
        self.config = config or PublisherConfig.from_env()
        self.db = PublisherDatabase(self.config.db_path)
        self.client = InstagramPublisher(self.config)
        self.supabase = SupabaseStorageClient(
            supabase_url=self.config.supabase_url,
            supabase_key=self.config.supabase_key,
            bucket_name=self.config.supabase_bucket
        )

    def format_caption(self, caption_text: str, hashtags: List[str]) -> str:
        """Combine caption copy with hashtags formatted cleanly for Instagram."""
        clean_tags = []
        for tag in hashtags:
            t = tag.strip().lstrip("#")
            if t:
                clean_tags.append(f"#{t}")
        tag_str = " ".join(clean_tags)
        if not tag_str:
            return caption_text.strip()
        return f"{caption_text.strip()}\n\n.\n.\n{tag_str}"

    def publish_reel(
        self,
        video_path: str,
        caption_text: str,
        hashtags: Optional[List[str]] = None,
        video_url: Optional[str] = None,
        scheduled_time: Optional[int] = None,
        dry_run: Optional[bool] = None
    ) -> PublishResult:
        """Execute publication or dry-run simulation of an Instagram Reel."""
        is_dry_run = dry_run if dry_run is not None else self.config.dry_run
        hashtags = hashtags or []
        pub_id = f"pub_{uuid.uuid4().hex[:12]}"
        full_caption = self.format_caption(caption_text, hashtags)

        vpath = Path(video_path)
        if not vpath.is_file():
            err_msg = f"Video file not found at: {video_path}"
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="FAILED",
                is_dry_run=is_dry_run,
                error_message=err_msg
            )
            return PublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=is_dry_run,
                error_message=err_msg
            )

        # Scheduled time validation: must be between 15 minutes and 75 days in future if provided
        if scheduled_time is not None:
            now_ts = int(time.time())
            min_ts = now_ts + (15 * 60)
            max_ts = now_ts + (75 * 24 * 3600)
            if scheduled_time < min_ts or scheduled_time > max_ts:
                err_msg = (
                    f"Scheduled time ({scheduled_time}) is invalid. "
                    f"Must be between 15 minutes ({min_ts}) and 75 days ({max_ts}) from now."
                )
                self.db.record_publication(
                    pub_id=pub_id,
                    video_path=video_path,
                    caption=full_caption,
                    hashtags=hashtags,
                    status="FAILED",
                    is_dry_run=is_dry_run,
                    scheduled_time=scheduled_time,
                    error_message=err_msg
                )
                return PublishResult(
                    publication_id=pub_id,
                    status="FAILED",
                    is_dry_run=is_dry_run,
                    scheduled_time=scheduled_time,
                    error_message=err_msg
                )

        # -------------------------------------------------------------
        # Dry-run execution path
        # -------------------------------------------------------------
        if is_dry_run:
            simulated_creation_id = f"mock_container_{uuid.uuid4().hex[:10]}"
            simulated_post_id = f"mock_post_{uuid.uuid4().hex[:10]}"
            status = "SCHEDULED" if scheduled_time else "DRY_RUN"
            simulated_video_url = video_url or (
                self.supabase.get_public_url(vpath.name)
                if self.config.supabase_url
                else f"https://mock-cdn.adsync.io/videos/{vpath.name}"
            )
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status=status,
                is_dry_run=True,
                creation_id=simulated_creation_id,
                post_id=simulated_post_id,
                permalink="https://www.instagram.com/reel/DRY_RUN_SIMULATED/",
                scheduled_time=scheduled_time,
                response_payload={
                    "mode": "dry_run",
                    "video_path": str(vpath.resolve()),
                    "simulated_video_url": simulated_video_url,
                    "caption_length": len(full_caption),
                    "hashtags_count": len(hashtags),
                    "simulated_container_id": simulated_creation_id
                }
            )
            return PublishResult(
                publication_id=pub_id,
                status=status,
                is_dry_run=True,
                creation_id=simulated_creation_id,
                post_id=simulated_post_id,
                permalink="https://www.instagram.com/reel/DRY_RUN_SIMULATED/",
                scheduled_time=scheduled_time
            )

        # -------------------------------------------------------------
        # Live Graph API execution path
        # -------------------------------------------------------------
        if not self.config.access_token or not self.config.instagram_account_id:
            err_msg = "Live publishing requires INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID."
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )
            return PublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )

        resolved_url = video_url
        if not resolved_url and self.config.supabase_url and self.config.supabase_key:
            try:
                resolved_url = self.supabase.upload_file(str(vpath), destination_path=vpath.name)
            except SupabaseStorageError as e:
                err_msg = f"Failed to upload video to Supabase: {str(e)}"
                self.db.record_publication(
                    pub_id=pub_id,
                    video_path=video_path,
                    caption=full_caption,
                    hashtags=hashtags,
                    status="FAILED",
                    is_dry_run=False,
                    error_message=err_msg
                )
                return PublishResult(
                    publication_id=pub_id,
                    status="FAILED",
                    is_dry_run=False,
                    error_message=err_msg
                )

        if not resolved_url and self.config.video_host_base_url:
            resolved_url = f"{self.config.video_host_base_url.rstrip('/')}/{vpath.name}"

        if not resolved_url:
            err_msg = (
                "Instagram Graph API requires a publicly accessible HTTPS video URL. "
                "Configure Supabase Storage in .env, specify video_url, or set VIDEO_HOST_BASE_URL."
            )
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )
            return PublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )

        try:
            # Step 1: Create Container
            creation_id = self.client.create_reel_container(
                video_url=resolved_url,
                caption=full_caption,
                scheduled_publish_time=scheduled_time
            )

            # Step 2: Poll Container Status until FINISHED
            max_wait_seconds = 180
            poll_interval = 5
            elapsed = 0
            container_ready = False

            while elapsed < max_wait_seconds:
                status_res = self.client.check_container_status(creation_id)
                code = status_res.get("status_code", "").upper()
                if code == "FINISHED":
                    container_ready = True
                    break
                elif code in ("ERROR", "EXPIRED"):
                    raise InstagramAPIError(
                        f"Container processing failed with status: {code}",
                        error_data=status_res
                    )
                time.sleep(poll_interval)
                elapsed += poll_interval

            if not container_ready:
                raise InstagramAPIError(
                    f"Container processing timed out after {max_wait_seconds} seconds."
                )

            # If scheduled, container creation completes the scheduling workflow
            if scheduled_time:
                self.db.record_publication(
                    pub_id=pub_id,
                    video_path=video_path,
                    caption=full_caption,
                    hashtags=hashtags,
                    status="SCHEDULED",
                    is_dry_run=False,
                    creation_id=creation_id,
                    scheduled_time=scheduled_time
                )
                return PublishResult(
                    publication_id=pub_id,
                    status="SCHEDULED",
                    is_dry_run=False,
                    creation_id=creation_id,
                    scheduled_time=scheduled_time
                )

            # Step 3: Publish Container
            post_id = self.client.publish_container(creation_id)
            permalink = self.client.get_media_permalink(post_id)

            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="PUBLISHED",
                is_dry_run=False,
                creation_id=creation_id,
                post_id=post_id,
                permalink=permalink
            )
            return PublishResult(
                publication_id=pub_id,
                status="PUBLISHED",
                is_dry_run=False,
                creation_id=creation_id,
                post_id=post_id,
                permalink=permalink
            )

        except InstagramAPIError as e:
            err_msg = str(e)
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg,
                response_payload=e.error_data
            )
            return PublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg,
                raw_response=e.error_data
            )
        except Exception as e:
            err_msg = f"Unexpected publisher error: {str(e)}"
            self.db.record_publication(
                pub_id=pub_id,
                video_path=video_path,
                caption=full_caption,
                hashtags=hashtags,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )
            return PublishResult(
                publication_id=pub_id,
                status="FAILED",
                is_dry_run=False,
                error_message=err_msg
            )

