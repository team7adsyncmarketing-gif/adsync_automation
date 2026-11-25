"""Unit tests for Phase 4A Instagram Reels Publisher and Supabase Storage."""
import unittest
import tempfile
import os
import time
import gc
from pathlib import Path
from publisher.config import PublisherConfig
from publisher.storage import PublisherDatabase
from publisher.manager import ReelPublishManager
from publisher.client import InstagramPublisher, InstagramAPIError
from publisher.supabase_uploader import SupabaseStorageClient, SupabaseStorageError


class TestInstagramPublisher(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_trends.db"
        self.config = PublisherConfig(
            access_token="fake_token_12345",
            instagram_account_id="17841400000000000",
            dry_run=True,
            db_path=self.db_path,
            supabase_url="https://mockproject.supabase.co",
            supabase_key="mock_supabase_key_abcdef123456",
            supabase_bucket="adsync-reels"
        )
        self.manager = ReelPublishManager(self.config)

        # Create a dummy video file for testing
        self.dummy_video = Path(self.tmp_dir.name) / "test_reel.mp4"
        with open(self.dummy_video, "wb") as f:
            f.write(b"\x00" * 1024)

    def tearDown(self):
        # Allow Windows file handles on SQLite db to close cleanly before cleanup
        del self.manager
        gc.collect()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_database_schema_initialization(self):
        """Verify publication ledger table is initialized properly."""
        db = PublisherDatabase(self.db_path)
        pubs = db.list_publications()
        self.assertEqual(len(pubs), 0)

    def test_format_caption_with_hashtags(self):
        """Verify hashtags are sanitized and appended cleanly."""
        cap = self.manager.format_caption(
            "Why views don't pay bills.",
            ["marketing", "#leadgen", "business "]
        )
        self.assertIn("Why views don't pay bills.", cap)
        self.assertIn("#marketing #leadgen #business", cap)

    def test_dry_run_publication(self):
        """Verify dry run generates simulated ids, writes to db, and does not call network."""
        res = self.manager.publish_reel(
            video_path=str(self.dummy_video),
            caption_text="Test Caption for Reels",
            hashtags=["adsync", "automation"],
            dry_run=True
        )
        self.assertEqual(res.status, "DRY_RUN")
        self.assertTrue(res.is_dry_run)
        self.assertTrue(res.creation_id.startswith("mock_container_"))
        self.assertTrue(res.post_id.startswith("mock_post_"))
        self.assertIn("DRY_RUN_SIMULATED", res.permalink)

        # Verify DB record
        record = self.manager.db.get_publication(res.publication_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "DRY_RUN")
        self.assertEqual(record["is_dry_run"], 1)
        self.assertEqual(record["hashtags"], ["adsync", "automation"])

    def test_missing_video_fails_safely(self):
        """Verify publisher records failure if video path does not exist."""
        res = self.manager.publish_reel(
            video_path=str(Path(self.tmp_dir.name) / "non_existent.mp4"),
            caption_text="Test Caption",
            dry_run=True
        )
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Video file not found", res.error_message)

        record = self.manager.db.get_publication(res.publication_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "FAILED")

    def test_scheduling_validation(self):
        """Verify invalid schedule timestamps are rejected."""
        # Past timestamp
        past_ts = int(time.time()) - 3600
        res = self.manager.publish_reel(
            video_path=str(self.dummy_video),
            caption_text="Scheduled post",
            scheduled_time=past_ts,
            dry_run=True
        )
        self.assertEqual(res.status, "FAILED")
        self.assertIn("invalid", res.error_message)

        # Valid future timestamp (1 hour ahead)
        future_ts = int(time.time()) + 3600
        res_valid = self.manager.publish_reel(
            video_path=str(self.dummy_video),
            caption_text="Scheduled post",
            scheduled_time=future_ts,
            dry_run=True
        )
        self.assertEqual(res_valid.status, "SCHEDULED")
        self.assertEqual(res_valid.scheduled_time, future_ts)

    def test_token_masking(self):
        """Verify secrets are redacted in error messages."""
        client = InstagramPublisher(self.config)
        masked = client._mask_token(f"Authentication failed with token {self.config.access_token} error")
        self.assertNotIn("fake_token_12345", masked)
        self.assertIn("REDACTED_TOKEN", masked)

    def test_supabase_public_url_builder(self):
        """Verify SupabaseStorageClient builds clean public URLs without exposing keys."""
        sb_client = SupabaseStorageClient(
            supabase_url="https://xyz.supabase.co",
            supabase_key="secret_key_999",
            bucket_name="adsync-reels"
        )
        url = sb_client.get_public_url("sample_short.mp4")
        self.assertEqual(
            url,
            "https://xyz.supabase.co/storage/v1/object/public/adsync-reels/sample_short.mp4"
        )
        self.assertNotIn("secret_key_999", url)

    def test_supabase_secret_masking(self):
        """Verify SupabaseStorageClient masks credentials in error strings."""
        sb_client = SupabaseStorageClient(
            supabase_url="https://xyz.supabase.co",
            supabase_key="secret_key_999",
            bucket_name="adsync-reels"
        )
        masked = sb_client._mask_key("Error communicating with key secret_key_999 in authorization")
        self.assertNotIn("secret_key_999", masked)
        self.assertIn("REDACTED_SUPABASE_KEY", masked)


if __name__ == "__main__":
    unittest.main()
