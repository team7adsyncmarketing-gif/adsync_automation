"""Comprehensive offline test suite for AdSync Trend Engine."""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any, List, Dict, Optional
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from trend_engine.config import mask_key, EngineConfig
from trend_engine.providers.base import (
    AuthenticationError,
    PaymentRequiredError,
    RateLimitError,
    ForbiddenError,
    ProviderServerError,
    TrendProviderError,
)
from trend_engine.providers.social_fetch import (
    SocialFetchClient,
    extract_media_list,
    _safe_int,
)
from trend_engine.storage.models import ReelItem, ReelAnalysis, AdSyncIdea, CompetitorProfile, ReelSnapshot
from trend_engine.storage.database import DatabaseRepository
from trend_engine.analysis.categorization import classify_reel_category
from trend_engine.analysis.hook_extractor import (
    extract_hook_sentence,
    classify_hook_pattern,
    identify_content_format,
    compute_virality_score,
    analyze_reel,
)
from trend_engine.analysis.idea_generator import generate_adsync_idea, generate_batch_ideas
from trend_engine.analysis.scoring import (
    EngagementScoringEngine,
    ScoringWeights,
    EngagementRates,
    CreatorBenchmark,
    ReelScoreBreakdown,
)
from trend_engine.analysis.trending import (
    TrendingDetectionEngine,
    TrendingEngineConfig,
    TrendingReelResult,
    EmergingTopicCluster,
    TrendingAnalysisReport,
)
from trend_engine.analysis.competitors import (
    COMPETITOR_CATEGORIES,
    CompetitorPerformanceSummary,
    CompetitorComparisonReport,
    CompetitorIntelligenceEngine,
)
from trend_engine.analysis.hook_format import (
    HOOK_CATEGORIES,
    VIDEO_FORMATS,
    CTA_TYPES,
    HookDetail,
    FormatDetail,
    StructureDetail,
    CTADetail,
    ReelHookFormatAnalysis,
    PatternPerformanceReport,
    NicheContentRecommendation,
    HookFormatIntelligenceEngine,
)
from trend_engine.analysis.creative_director import (
    VALID_STYLES,
    VALID_VOICES,
    VALID_MUSIC,
    CreativeDecision,
    ScenePlan,
    CreativeBrief,
    AICreativeDirector,
)
from trend_engine.reporting.daily_report import DailyReportGenerator
from trend_engine.run_engine import test_live_single_reel


class TestTrendEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.fixtures_path = cls.base_dir / "data" / "fixtures" / "sample_trending_reels.json"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_trends.db"
        self.db = DatabaseRepository(self.db_path)
        self.config = EngineConfig(
            api_key="test_sample_key_12345",
            base_url="https://api.socialfetch.dev",
            db_path=self.db_path,
            force_mock_mode=True,
            fixtures_path=self.fixtures_path,
        )

    def tearDown(self):
        del self.db
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # =========================================================================
    # 1. Config & Masking Tests
    # =========================================================================
    def test_key_masking(self):
        self.assertEqual(mask_key(""), "<EMPTY>")
        self.assertEqual(mask_key(None), "<EMPTY>")
        self.assertEqual(mask_key("short"), "***")
        masked = mask_key("sf_live_abc123456789xyz")
        self.assertTrue(masked.startswith("sf_..."))
        self.assertTrue(masked.endswith("9xyz"))
        self.assertNotIn("12345678", masked)

    def test_force_mock_mode_respected(self):
        cfg_forced = EngineConfig(
            api_key="test_sample_key",
            base_url="https://api.socialfetch.dev",
            db_path=self.db_path,
            force_mock_mode=True,
            fixtures_path=self.fixtures_path,
        )
        client = SocialFetchClient(cfg_forced)
        self.assertTrue(client.use_mock)
        reels = client.fetch_trending_reels()
        self.assertTrue(all(r.is_mock for r in reels))

    # =========================================================================
    # 2. Extract Media List & Safe Helpers
    # =========================================================================
    def test_safe_int_helper(self):
        self.assertEqual(_safe_int(100), 100)
        self.assertEqual(_safe_int("1,500"), 1500)
        self.assertEqual(_safe_int("250"), 250)
        self.assertEqual(_safe_int(None, 42), 42)
        self.assertEqual(_safe_int("not_a_number", 0), 0)
        self.assertEqual(_safe_int([], 0), 0)

    def test_extract_media_list_all_envelope_types(self):
        # Case a: Top-level list
        fixture_a = [{"id": "a1", "code": "A1"}]
        self.assertEqual(extract_media_list(fixture_a), fixture_a)

        # Case b: Dict with data.media
        fixture_b = {"data": {"media": [{"id": "b2", "code": "B2"}]}}
        self.assertEqual(extract_media_list(fixture_b), [{"id": "b2", "code": "B2"}])

        # Case c: Dict with reels
        fixture_c = {"reels": [{"id": "c3", "code": "C3"}]}
        self.assertEqual(extract_media_list(fixture_c), [{"id": "c3", "code": "C3"}])

        # Additional common envelopes: data.reels, data.items, items, results
        self.assertEqual(extract_media_list({"data": {"reels": [{"id": "r1"}]}}), [{"id": "r1"}])
        self.assertEqual(extract_media_list({"data": [{"id": "d1"}]}), [{"id": "d1"}])
        self.assertEqual(extract_media_list({"items": [{"id": "i1"}]}), [{"id": "i1"}])
        self.assertEqual(extract_media_list({"results": [{"id": "res1"}]}), [{"id": "res1"}])
        self.assertEqual(extract_media_list({"media": [{"id": "m1"}]}), [{"id": "m1"}])

        # Case d: Empty payloads
        self.assertEqual(extract_media_list([]), [])
        self.assertEqual(extract_media_list({}), [])
        self.assertEqual(extract_media_list({"data": {"media": []}}), [])
        self.assertEqual(extract_media_list({"reels": []}), [])
        self.assertEqual(extract_media_list({"data": []}), [])
        self.assertEqual(extract_media_list(None), [])
        self.assertEqual(extract_media_list(""), [])

        # Non-media dicts (should return [] and never raise KeyError)
        self.assertEqual(extract_media_list({"message": "Rate limit exceeded"}), [])
        self.assertEqual(extract_media_list({"error": "Unauthorized"}), [])
        self.assertEqual(extract_media_list({"data": {"status": "fail"}}), [])

    # =========================================================================
    # 3. Offline Fixture Tests (a, b, c, d, e) for Live Client Methods
    # =========================================================================
    def _create_mock_response(self, payload_dict_or_list: Any, status: int = 200, headers: dict = None):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload_dict_or_list).encode("utf-8")
        mock_resp.status = status
        mock_resp.code = status
        mock_resp.headers = headers or {"x-rate-limit-remaining": "50", "content-type": "application/json"}
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    def test_fixture_a_list_response_offline(self):
        """Fixture a: Top-level list response."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = [
            {
                "id": 101,
                "code": "C_List101",
                "caption": "How to scale your Meta Ads in 2026 #marketing #ads",
                "user": {"username": "adsexpert", "full_name": "Ads Expert"},
                "play_count": 150000,
                "like_count": 7500,
                "comment_count": 420,
                "share_count": 890,
                "hashtags": ["marketing", "ads"],
                "music_metadata": {"title": "Viral Trend Beat", "artist_name": "Artist 1"},
            }
        ]
        mock_resp = self._create_mock_response(payload)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            # Test probe_single_live_reel
            probe_res = client.probe_single_live_reel()
            self.assertEqual(probe_res["status"], "SUCCESS")
            self.assertEqual(probe_res["status_code"], 200)
            sample = probe_res["reel_sample"]
            self.assertEqual(sample["shortcode"], "C_List101")
            self.assertEqual(sample["author"], "adsexpert")
            self.assertEqual(sample["plays"], 150000)
            self.assertEqual(sample["likes"], 7500)
            self.assertEqual(sample["audio"], "Viral Trend Beat")

            # Test _fetch_live_reels
            reels = client._fetch_live_reels()
            self.assertEqual(len(reels), 1)
            self.assertEqual(reels[0].reel_id, "101")
            self.assertEqual(reels[0].shortcode, "C_List101")
            self.assertFalse(reels[0].is_mock)

    def test_fixture_b_dict_data_media_offline(self):
        """Fixture b: Dictionary with data.media (prevents KeyError: 0)."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = {
            "data": {
                "media": [
                    {
                        "pk": 202,
                        "shortcode": "C_Media202",
                        "edge_media_to_caption": {"edges": [{"node": {"text": "Stop boosting posts! Use Ads Manager."}}]},
                        "owner": {"username": "growth_hacker"},
                        "view_count": 85000,
                        "edge_media_preview_like": {"count": 3400},
                        "edge_media_to_comment": {"count": 210},
                        "music_info": {"music_asset_info": {"title": "Sound of Growth"}},
                    }
                ]
            }
        }
        mock_resp = self._create_mock_response(payload)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            # Verify probe does NOT raise KeyError: 0
            probe_res = client.probe_single_live_reel()
            self.assertEqual(probe_res["status"], "SUCCESS")
            self.assertEqual(probe_res["reel_sample"]["shortcode"], "C_Media202")
            self.assertEqual(probe_res["reel_sample"]["author"], "growth_hacker")
            self.assertEqual(probe_res["reel_sample"]["plays"], 85000)
            self.assertEqual(probe_res["reel_sample"]["likes"], 3400)

            # Verify _fetch_live_reels parses data.media correctly
            reels = client._fetch_live_reels()
            self.assertEqual(len(reels), 1)
            self.assertEqual(reels[0].shortcode, "C_Media202")
            self.assertEqual(reels[0].author_username, "growth_hacker")

    def test_social_fetch_v2_exact_schema_offline(self):
        """Tests exact Social Fetch v2 payload with data.media, metrics object, and owner.handle."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = {
            "data": {
                "lookupStatus": "found",
                "media": [
                    {
                        "kind": "reel",
                        "id": "3124567890123456789",
                        "shortcode": "CUxxxxxxAB",
                        "url": "https://www.instagram.com/reel/CUxxxxxxAB/",
                        "caption": "Exploring the mountains this weekend! #travel #nature",
                        "owner": {
                            "id": "123456789",
                            "handle": "mountain_explorer",
                            "fullName": "Mountain Explorer",
                            "isVerified": True,
                        },
                        "metrics": {
                            "playCount": 452000,
                            "likeCount": 38400,
                            "commentCount": 1250,
                            "shareCount": 4300,
                            "saveCount": 5100,
                        },
                        "videoUrl": "https://instagram.fccu3-1.fna.fbcdn.net/v/example_video.mp4",
                        "audio": {
                            "id": "9876543210",
                            "title": "Original Audio",
                            "artist": "mountain_explorer",
                            "isTrending": True,
                        },
                    }
                ]
            },
            "meta": {
                "version": "v2",
                "creditsCharged": 1,
            }
        }
        mock_resp = self._create_mock_response(payload)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            probe_res = client.probe_single_live_reel()
            self.assertEqual(probe_res["status"], "SUCCESS")
            sample = probe_res["reel_sample"]
            # Author handle extracted without falling back to 'creator'
            self.assertEqual(sample["author"], "mountain_explorer")
            # Metrics extracted accurately from metrics object
            self.assertEqual(sample["plays"], 452000)
            self.assertEqual(sample["likes"], 38400)
            self.assertEqual(sample["comments"], 1250)
            self.assertEqual(sample["shares"], 4300)
            self.assertEqual(sample["audio"], "Original Audio")

            # Verify _fetch_live_reels
            reels = client._fetch_live_reels()
            self.assertEqual(len(reels), 1)
            r = reels[0]
            self.assertEqual(r.author_username, "mountain_explorer")
            self.assertEqual(r.author_full_name, "Mountain Explorer")
            self.assertEqual(r.play_count, 452000)
            self.assertEqual(r.like_count, 38400)
            self.assertEqual(r.comment_count, 1250)
            self.assertEqual(r.share_count, 4300)
            self.assertGreater(r.engagement_rate, 0.0)

    def test_null_metrics_preserved_as_none_offline(self):
        """Verifies that missing or null metrics are preserved as None, never fabricated as 0."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = {
            "data": {
                "media": [
                    {
                        "id": "reel_null_metrics",
                        "shortcode": "CNullMetrics",
                        "caption": "Reel with hidden likes and unrecorded plays",
                        "owner": {
                            "handle": "private_creator",
                        },
                        "metrics": {
                            "playCount": None,
                            "likeCount": None,
                            "commentCount": None,
                            "shareCount": None,
                        },
                    }
                ]
            }
        }
        mock_resp = self._create_mock_response(payload)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            reels = client._fetch_live_reels()
            self.assertEqual(len(reels), 1)
            r = reels[0]
            self.assertEqual(r.author_username, "private_creator")
            # Must be None, not 0!
            self.assertIsNone(r.play_count)
            self.assertIsNone(r.like_count)
            self.assertIsNone(r.comment_count)
            self.assertIsNone(r.share_count)
            self.assertIsNone(r.engagement_rate)

            # Virality score must also be None (not invented)
            from trend_engine.analysis.hook_extractor import analyze_reel
            analysis = analyze_reel(r)
            self.assertIsNone(analysis.virality_score)

            # Idea generation must handle None without crashing and flag discovery batch
            from trend_engine.analysis.idea_generator import generate_adsync_idea
            idea = generate_adsync_idea(r, analysis)
            self.assertIn("Discovery batch candidate", idea.reasoning)
            self.assertGreaterEqual(idea.opportunity_score, 50.0)

    def test_fixture_c_dict_reels_offline(self):
        """Fixture c: Dictionary with reels key."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = {
            "reels": [
                {
                    "id": "reel_303",
                    "code": "C_Reels303",
                    "caption": "Lead gen funnels for real estate agents #leadgen",
                    "author_username": "realtor_growth",
                    "views": 45000,
                    "likes": 2100,
                    "comments": 150,
                    "reshares": 310,
                }
            ]
        }
        mock_resp = self._create_mock_response(payload)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            probe_res = client.probe_single_live_reel()
            self.assertEqual(probe_res["status"], "SUCCESS")
            self.assertEqual(probe_res["reel_sample"]["shortcode"], "C_Reels303")
            self.assertEqual(probe_res["reel_sample"]["plays"], 45000)

            reels = client._fetch_live_reels()
            self.assertEqual(len(reels), 1)
            self.assertEqual(reels[0].shortcode, "C_Reels303")

    def test_fixture_d_empty_response_offline(self):
        """Fixture d: Empty responses ([], {"data": {"media": []}}, {})."""
        client = SocialFetchClient(self.config, use_mock=False)

        for empty_payload in [[], {}, {"data": {"media": []}}, {"reels": []}]:
            mock_resp = self._create_mock_response(empty_payload)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                # probe returns graceful EMPTY notice without crashing
                probe_res = client.probe_single_live_reel()
                self.assertEqual(probe_res["status"], "EMPTY_OR_UNEXPECTED_PAYLOAD")
                self.assertEqual(probe_res["status_code"], 200)

                # fetch returns empty list without crashing
                reels = client._fetch_live_reels()
                self.assertEqual(reels, [])

    def test_fixture_e_error_responses_offline(self):
        """Fixture e: Error responses (HTTP 401, 402, 403, 429, 500, payload errors)."""
        client = SocialFetchClient(self.config, use_mock=False)

        # 401 Unauthorized
        err_401 = urllib.error.HTTPError(
            url="http://test", code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b"Invalid key")
        )
        with patch("urllib.request.urlopen", side_effect=err_401):
            with self.assertRaises(AuthenticationError):
                client.probe_single_live_reel()

        # 402 Payment Required
        err_402 = urllib.error.HTTPError(
            url="http://test", code=402, msg="Payment Required", hdrs={}, fp=io.BytesIO(b"Out of credits")
        )
        with patch("urllib.request.urlopen", side_effect=err_402):
            with self.assertRaises(PaymentRequiredError):
                client.probe_single_live_reel()

        # 403 Forbidden
        err_403 = urllib.error.HTTPError(
            url="http://test", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"Access forbidden")
        )
        with patch("urllib.request.urlopen", side_effect=err_403):
            with self.assertRaises(ForbiddenError):
                client.probe_single_live_reel()

        # 429 Rate Limit with Retry-After header
        err_429 = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests",
            hdrs={"Retry-After": "45"}, fp=io.BytesIO(b"Rate limit reached")
        )
        with patch("urllib.request.urlopen", side_effect=err_429):
            with self.assertRaises(RateLimitError) as ctx:
                client.probe_single_live_reel()
            self.assertEqual(ctx.exception.retry_after, 45)

        # 500 Server Error
        err_500 = urllib.error.HTTPError(
            url="http://test", code=500, msg="Internal Server Error",
            hdrs={}, fp=io.BytesIO(b"Internal upstream error")
        )
        with patch("urllib.request.urlopen", side_effect=err_500):
            with self.assertRaises(ProviderServerError):
                client.probe_single_live_reel()

    def test_unexpected_payload_offline(self):
        """Unexpected payload (e.g. JSON error object returned with HTTP 200)."""
        client = SocialFetchClient(self.config, use_mock=False)
        payload = {"status": "fail", "message": "Account has been temporarily suspended"}
        mock_resp = self._create_mock_response(payload)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            probe_res = client.probe_single_live_reel()
            self.assertEqual(probe_res["status"], "EMPTY_OR_UNEXPECTED_PAYLOAD")
            self.assertIn("Account has been temporarily suspended", probe_res["message"])

            with self.assertRaises(TrendProviderError) as ctx:
                client._fetch_live_reels()
            self.assertIn("Account has been temporarily suspended", str(ctx.exception))

    # =========================================================================
    # 4. Single-Probe CLI Error Handling (Offline)
    # =========================================================================
    def test_cli_single_probe_safety_lock_offline(self):
        """CLI single-probe must reject execution when FORCE_MOCK_MODE=1 without network."""
        mock_cfg = EngineConfig(
            api_key="sfk_test_key_12345",
            base_url="https://api.socialfetch.dev",
            db_path=self.db_path,
            force_mock_mode=True,
            fixtures_path=self.fixtures_path,
        )
        with patch("trend_engine.run_engine.get_config", return_value=mock_cfg):
            # Must return 1 (blocked by safety lock) without calling urlopen
            with patch("urllib.request.urlopen") as mock_urlopen:
                ret = test_live_single_reel()
                self.assertEqual(ret, 1)
                mock_urlopen.assert_not_called()

    def test_cli_single_probe_offline_success(self):
        """CLI single-probe handles successful probe offline when mock unlocked."""
        mock_cfg = EngineConfig(
            api_key="sfk_test_key_12345",
            base_url="https://api.socialfetch.dev",
            db_path=self.db_path,
            force_mock_mode=False,
            fixtures_path=self.fixtures_path,
        )
        payload = [{"id": "cli_1", "code": "CLI1", "caption": "Test hook", "play_count": 100}]
        mock_resp = self._create_mock_response(payload)

        with patch("trend_engine.run_engine.get_config", return_value=mock_cfg):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ret = test_live_single_reel()
                self.assertEqual(ret, 0)

    def test_cli_single_probe_offline_payment_required(self):
        """CLI single-probe handles HTTP 402 cleanly with code 2."""
        mock_cfg = EngineConfig(
            api_key="sfk_test_key_12345",
            base_url="https://api.socialfetch.dev",
            db_path=self.db_path,
            force_mock_mode=False,
            fixtures_path=self.fixtures_path,
        )
        err_402 = urllib.error.HTTPError(
            url="http://test", code=402, msg="Payment Required", hdrs={}, fp=io.BytesIO(b"Zero credits")
        )
        with patch("trend_engine.run_engine.get_config", return_value=mock_cfg):
            with patch("urllib.request.urlopen", side_effect=err_402):
                ret = test_live_single_reel()
                self.assertEqual(ret, 2)

    # =========================================================================
    # 5. Mock Ingestion & Field Extraction
    # =========================================================================
    def test_mock_ingestion_and_field_extraction(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels()

        self.assertGreaterEqual(len(reels), 15)
        for r in reels:
            self.assertTrue(r.is_mock)
            self.assertTrue(r.reel_id)
            self.assertTrue(r.shortcode)
            self.assertTrue(r.url.startswith("https://www.instagram.com/reel/"))
            self.assertTrue(r.caption)
            self.assertGreater(r.play_count, 0)
            self.assertGreater(r.like_count, 0)
            self.assertIsInstance(r.hashtags, list)
            self.assertGreater(len(r.hashtags), 0)
            self.assertGreaterEqual(r.engagement_rate, 0.0)

    # =========================================================================
    # 6. SQLite Persistence & Queries
    # =========================================================================
    def test_database_persistence(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels(limit=5)

        saved = self.db.save_reels(reels)
        self.assertEqual(saved, 5)

        retrieved = self.db.get_reels(is_mock=True)
        self.assertEqual(len(retrieved), 5)
        self.assertEqual({r.reel_id for r in retrieved}, {r.reel_id for r in reels})

        # Upsert test
        reels[0].like_count += 500
        self.db.save_reels([reels[0]])
        updated = self.db.get_reels(is_mock=True)
        self.assertEqual(len(updated), 5)

    # =========================================================================
    # 7. Marketing Categorization Tests
    # =========================================================================
    def test_marketing_categorization(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels()

        categories_found = set()
        for r in reels:
            cat, conf = classify_reel_category(r)
            categories_found.add(cat)
            self.assertGreaterEqual(conf, 0.40)
            self.assertLessEqual(conf, 1.0)

        # Ensure major target categories are recognized
        self.assertIn("Meta Ads", categories_found)
        self.assertIn("Instagram Marketing", categories_found)
        self.assertIn("Lead Generation", categories_found)
        self.assertIn("Real Estate Marketing", categories_found)
        self.assertIn("Marketing Automation", categories_found)

    # =========================================================================
    # 8. Hook Extraction & Content Formatting
    # =========================================================================
    def test_hook_and_format_analysis(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels()

        analyses = [analyze_reel(r) for r in reels]
        self.assertEqual(len(analyses), len(reels))

        for a in analyses:
            self.assertTrue(a.hook_text)
            self.assertTrue(a.hook_type)
            self.assertTrue(a.hook_psychology)
            self.assertTrue(a.content_format)
            self.assertGreater(a.virality_score, 0.0)

    # =========================================================================
    # 9. AdSync Idea Generation & Phase 1 Style Routing
    # =========================================================================
    def test_adsync_idea_generator(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels()
        analyses = [analyze_reel(r) for r in reels]

        ideas = generate_batch_ideas(reels, analyses)
        self.assertGreaterEqual(len(ideas), 5)

        valid_phase1_styles = {
            "deep-dive",
            "inside-out",
            "night-file",
            "paper-atlas",
            "stick-story",
            "tall-tale",
        }

        for idea in ideas:
            self.assertTrue(idea.topic)
            self.assertEqual(len(idea.hooks), 3)  # Exactly 3 original hooks
            self.assertTrue(idea.target_audience)
            self.assertTrue(idea.business_problem)
            self.assertTrue(idea.call_to_action)
            self.assertIn(idea.faceless_short_style, valid_phase1_styles)
            self.assertGreater(idea.opportunity_score, 0.0)
            self.assertTrue(idea.reasoning)

    # =========================================================================
    # 10. Daily Intelligence Report Generation
    # =========================================================================
    def test_daily_report_generation(self):
        client = SocialFetchClient(self.config, use_mock=True)
        reels = client.fetch_trending_reels()
        self.db.save_reels(reels)

        analyses = [analyze_reel(r) for r in reels]
        self.db.save_analyses(analyses)

        ideas = generate_batch_ideas(reels, analyses)
        self.db.save_ideas(ideas)

        reporter = DailyReportGenerator(self.db, output_dir=Path(self.temp_dir.name) / "reports")
        report_md = reporter.generate(is_mock=True)

        self.assertIn("DATA SOURCE NOTICE: MOCK DATA MODE", report_md)
        self.assertIn("1. Executive Trend Summary", report_md)
        self.assertIn("2. Engagement Metrics & Metadata Completeness Audit", report_md)
        self.assertIn("Dominant Content Formats", report_md)
        self.assertIn("Strongest Hook Patterns", report_md)
        self.assertIn("Category Performance", report_md)
        self.assertIn("Top Marketing-Related Hooks", report_md)
        self.assertIn("Top Ranked AdSync Marketing Reel Concepts", report_md)
        self.assertIn("Three Original Opening Hooks", report_md)

    def test_mock_and_live_report_strict_isolation(self):
        """Proves that mock data never leaks into live reports, and live data never leaks into mock reports."""
        client = SocialFetchClient(self.config, use_mock=True)
        mock_reels = client.fetch_trending_reels()
        self.db.save_reels(mock_reels)
        mock_analyses = [analyze_reel(r) for r in mock_reels]
        self.db.save_analyses(mock_analyses)
        mock_ideas = generate_batch_ideas(mock_reels, mock_analyses)
        self.db.save_ideas(mock_ideas)

        # Insert 3 simulated live reels (is_mock = False), all non-marketing/irrelevant
        live_reels = [
            ReelItem(
                reel_id=f"live_{i}",
                shortcode=f"LiveCode_{i}",
                url=f"https://www.instagram.com/reel/LiveCode_{i}/",
                caption=f"Soccer and college sports clip #{i} #sports #football",
                author_username=f"sports_page_{i}",
                play_count=50000 * i,
                like_count=2000 * i,
                is_mock=False,
            )
            for i in range(1, 4)
        ]
        self.db.save_reels(live_reels)
        live_analyses = [analyze_reel(r) for r in live_reels]
        self.db.save_analyses(live_analyses)
        live_ideas = generate_batch_ideas(live_reels, live_analyses)
        self.assertEqual(len(live_ideas), 0)  # All are Other / Irrelevant
        self.db.save_ideas(live_ideas)

        # Verify DB total counts
        total_in_db = len(mock_reels) + len(live_reels)
        self.assertEqual(self.db.get_summary_stats(is_mock=None)["total_reels"], total_in_db)

        # Generate LIVE report
        reporter = DailyReportGenerator(self.db, output_dir=Path(self.temp_dir.name) / "reports_iso")
        live_report_md = reporter.generate(is_mock=False)

        # Live report MUST reflect ONLY live records
        self.assertIn("Total Reels Retrieved in Batch:** 3", live_report_md)
        self.assertIn("Marketing Relevant Reels:** 0", live_report_md)
        self.assertIn("Irrelevant / Non-Marketing Reels:** 3", live_report_md)
        self.assertIn("AdSync Concepts Generated:** 0", live_report_md)
        # Mock shortcodes or authors MUST NOT appear in live report
        for mr in mock_reels:
            self.assertNotIn(mr.shortcode, live_report_md)
            self.assertNotIn(f"@{mr.author_username}", live_report_md)
        # Mock ideas MUST NOT appear in live report
        for mi in mock_ideas:
            self.assertNotIn(mi.topic, live_report_md)

        # Generate MOCK report
        mock_report_md = reporter.generate(is_mock=True)

        # Mock report MUST reflect ONLY mock records
        self.assertIn(f"Total Reels Retrieved in Batch:** {len(mock_reels)}", mock_report_md)
        self.assertIn(f"Marketing Relevant Reels:** {len(mock_reels)}", mock_report_md)
        self.assertIn("Irrelevant / Non-Marketing Reels:** 0", mock_report_md)
        self.assertIn(f"AdSync Concepts Generated:** {len(mock_ideas)}", mock_report_md)
        # Live shortcodes or authors MUST NOT appear in mock report
        for lr in live_reels:
            self.assertNotIn(lr.shortcode, mock_report_md)
            self.assertNotIn(f"@{lr.author_username}", mock_report_md)

    def test_fetch_reels_by_keyword_mock_mode(self):
        """Verify fetch_reels_by_keyword filters mock data properly and supports pagination."""
        client = SocialFetchClient(self.config, use_mock=True)

        for term in SocialFetchClient.SUPPORTED_SEARCH_TERMS:
            items, next_cursor = client.fetch_reels_by_keyword(term, limit=3)
            self.assertIsInstance(items, list)
            self.assertGreater(len(items), 0)
            self.assertTrue(all(isinstance(r, ReelItem) for r in items))
            self.assertTrue(all(r.is_mock for r in items))

        # Test pagination with cursor
        page1, cursor1 = client.fetch_reels_by_keyword("digital marketing", limit=2)
        self.assertEqual(len(page1), 2)
        self.assertIsNotNone(cursor1)

        page2, cursor2 = client.fetch_reels_by_keyword("digital marketing", limit=2, cursor=cursor1)
        self.assertEqual(len(page2), 2)
        # Ensure page 1 and page 2 returned different items
        self.assertNotEqual(page1[0].reel_id, page2[0].reel_id)

    def test_fetch_reels_by_keyword_live_mocked_network(self):
        """Verify fetch_reels_by_keyword live execution path with mocked HTTP responses."""
        client = SocialFetchClient(self.config, use_mock=False)
        client.api_key = "test_sfk_12345"

        sample_api_response = {
            "meta": {"version": "v2", "creditsCharged": 1},
            "data": {
                "media": [
                    {
                        "id": "kw_reel_1001",
                        "shortcode": "CKW1001",
                        "url": "https://www.instagram.com/reel/CKW1001/",
                        "caption": "How to scale Meta Ads for lead generation in 2026 #metaads #leadgen",
                        "createdAt": "2026-11-20T12:00:00Z",
                        "owner": {"handle": "marketing_pro", "fullName": "Marketing Pro"},
                        "metrics": {"playCount": 54000, "likeCount": 3200, "commentCount": 180, "shareCount": None},
                        "hashtags": ["metaads", "leadgen"]
                    }
                ],
                "page": {"hasMore": True, "nextCursor": "cursor_page_2_abc"}
            }
        }

        # Mock urllib response
        mock_body = json.dumps(sample_api_response)
        with patch.object(client, "_http_get", return_value=(200, mock_body, {"x-credits-remaining": "49"})) as mock_get:
            items, next_cursor = client.fetch_reels_by_keyword("Meta Ads", limit=10)

            # Verify call endpoint and parameters
            self.assertEqual(mock_get.call_count, 1)
            called_url = mock_get.call_args[0][0]
            self.assertIn("/v2/instagram/reels/search", called_url)
            self.assertIn("query=Meta+Ads", called_url)

            # Verify parsed items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].shortcode, "CKW1001")
            self.assertEqual(items[0].author_username, "marketing_pro")
            self.assertEqual(items[0].play_count, 54000)
            self.assertEqual(items[0].like_count, 3200)
            self.assertEqual(next_cursor, "cursor_page_2_abc")
            self.assertFalse(items[0].is_mock)

    def test_fetch_reels_by_keyword_empty_query_validation(self):
        """Verify empty or whitespace query is rejected with ValueError."""
        client = SocialFetchClient(self.config, use_mock=True)
        with self.assertRaises(ValueError):
            client.fetch_reels_by_keyword("")
        with self.assertRaises(ValueError):
            client.fetch_reels_by_keyword("   ")

    def test_fetch_reels_by_hashtag_mock_mode(self):
        """Verify fetch_reels_by_hashtag filters mock data and supports pagination across target hashtags."""
        client = SocialFetchClient(self.config, use_mock=True)

        for tag in SocialFetchClient.SUPPORTED_HASHTAGS:
            items, next_cursor = client.fetch_reels_by_hashtag(tag, limit=3)
            self.assertIsInstance(items, list)
            self.assertGreater(len(items), 0)
            self.assertTrue(all(isinstance(r, ReelItem) for r in items))
            self.assertTrue(all(r.is_mock for r in items))

        # Test pagination with cursor
        page1, cursor1 = client.fetch_reels_by_hashtag("leadgeneration", limit=2)
        self.assertEqual(len(page1), 2)
        self.assertIsNotNone(cursor1)

        page2, cursor2 = client.fetch_reels_by_hashtag("leadgeneration", limit=2, cursor=cursor1)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].reel_id, page2[0].reel_id)

    def test_fetch_reels_by_hashtag_live_mocked_network(self):
        """Verify fetch_reels_by_hashtag live execution path with mocked HTTP responses."""
        client = SocialFetchClient(self.config, use_mock=False)
        client.api_key = "test_sfk_12345"

        sample_api_response = {
            "meta": {"version": "v2", "creditsCharged": 1},
            "data": {
                "media": [
                    {
                        "id": "tag_reel_2001",
                        "shortcode": "CTAG2001",
                        "url": "https://www.instagram.com/reel/CTAG2001/",
                        "caption": "Proven #b2bmarketing framework for agency growth",
                        "createdAt": "2026-11-21T10:00:00Z",
                        "owner": {"handle": "b2b_agency_scaler", "fullName": "Agency Scaler"},
                        "metrics": {"playCount": 78000, "likeCount": 4200, "commentCount": 310, "shareCount": 1200},
                        "hashtags": ["b2bmarketing", "agencygrowth"]
                    }
                ],
                "page": {"hasMore": True, "nextCursor": "cursor_tag_page_2"}
            }
        }

        mock_body = json.dumps(sample_api_response)
        with patch.object(client, "_http_get", return_value=(200, mock_body, {"x-credits-remaining": "48"})) as mock_get:
            items, next_cursor = client.fetch_reels_by_hashtag("b2bmarketing", limit=10)

            # Verify call endpoint and parameters
            self.assertEqual(mock_get.call_count, 1)
            called_url = mock_get.call_args[0][0]
            self.assertIn("/v2/instagram/hashtags/b2bmarketing/media", called_url)
            self.assertIn("tab=reels", called_url)

            # Verify parsed items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].shortcode, "CTAG2001")
            self.assertEqual(items[0].author_username, "b2b_agency_scaler")
            self.assertEqual(items[0].play_count, 78000)
            self.assertEqual(items[0].like_count, 4200)
            self.assertEqual(items[0].comment_count, 310)
            self.assertEqual(items[0].share_count, 1200)
            self.assertEqual(next_cursor, "cursor_tag_page_2")
            self.assertFalse(items[0].is_mock)

    def test_fetch_reels_by_hashtag_validation(self):
        """Verify empty hashtag is rejected and leading hash is stripped."""
        client = SocialFetchClient(self.config, use_mock=True)
        with self.assertRaises(ValueError):
            client.fetch_reels_by_hashtag("")
        with self.assertRaises(ValueError):
            client.fetch_reels_by_hashtag("   ")

        # Calling with leading '#' should work cleanly
        items, _ = client.fetch_reels_by_hashtag("#metaads", limit=1)
        self.assertEqual(len(items), 1)

    # =========================================================================
    # Creator Discovery Tests (Stage 3)
    # =========================================================================

    def test_fetch_reels_by_creator_mock_mode(self):
        """Verify fetch_reels_by_creator mock mode returns ReelItems, profile_info, and supports pagination."""
        client = SocialFetchClient(self.config, use_mock=True)

        # Test valid handle
        items, profile, cursor = client.fetch_reels_by_creator("alex_growth_media", limit=3)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertTrue(all(isinstance(r, ReelItem) for r in items))
        self.assertTrue(all(r.is_mock for r in items))
        self.assertIsInstance(profile, dict)
        self.assertEqual(profile.get("handle"), "alex_growth_media")
        self.assertIn("counts", profile)
        self.assertIn("followers", profile["counts"])

        # Test pagination with cursor
        page1, profile1, cursor1 = client.fetch_reels_by_creator("growth_creator", limit=2)
        self.assertEqual(len(page1), 2)
        self.assertIsNotNone(cursor1)

        page2, profile2, cursor2 = client.fetch_reels_by_creator("growth_creator", limit=2, cursor=cursor1)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].reel_id, page2[0].reel_id)

    def test_fetch_reels_by_creator_live_mocked_network(self):
        """Verify fetch_reels_by_creator live execution path with mocked HTTP responses and profile extraction."""
        client = SocialFetchClient(self.config, use_mock=False)
        client.api_key = "test_sfk_12345"

        sample_api_response = {
            "meta": {"version": "v2", "creditsCharged": 2},
            "data": {
                "lookupStatus": "found",
                "profile": {
                    "id": "user_998877",
                    "handle": "meta_ads_expert",
                    "displayName": "Meta Ads Growth Expert",
                    "bio": "Scaling 7-figure e-commerce brands with Meta ads & funnels.",
                    "avatarUrl": "https://cdn.socialfetch.dev/avatars/user_998877.jpg",
                    "verified": True,
                    "privateAccount": False,
                    "counts": {
                        "posts": 142,
                        "followers": 128500,
                        "following": 412
                    }
                },
                "recentMedia": [
                    {
                        "id": "creator_reel_5001",
                        "shortcode": "CCREAT5001",
                        "url": "https://www.instagram.com/reel/CCREAT5001/",
                        "caption": "How we lowered CPA by 42% on Meta Ads in Q3 #metaads #growth",
                        "createdAt": "2026-11-22T14:30:00Z",
                        "owner": {"handle": "meta_ads_expert", "fullName": "Meta Ads Growth Expert"},
                        "metrics": {"playCount": 115000, "likeCount": 6800, "commentCount": 420, "shareCount": 2100},
                        "hashtags": ["metaads", "growth"]
                    }
                ],
                "page": {"hasMore": False, "nextCursor": None}
            }
        }

        mock_body = json.dumps(sample_api_response)
        with patch.object(client, "_http_get", return_value=(200, mock_body, {"x-credits-remaining": "46"})) as mock_get:
            items, profile, next_cursor = client.fetch_reels_by_creator("meta_ads_expert", limit=5)

            # Verify call endpoint and query parameters
            self.assertEqual(mock_get.call_count, 1)
            called_url = mock_get.call_args[0][0]
            self.assertIn("/v2/instagram/profiles/meta_ads_expert", called_url)
            self.assertIn("include=recentMedia", called_url)

            # Verify profile metadata
            self.assertIsInstance(profile, dict)
            self.assertEqual(profile.get("handle"), "meta_ads_expert")
            self.assertEqual(profile.get("displayName"), "Meta Ads Growth Expert")
            self.assertTrue(profile.get("verified"))
            self.assertEqual(profile.get("counts", {}).get("followers"), 128500)

            # Verify parsed items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].shortcode, "CCREAT5001")
            self.assertEqual(items[0].author_username, "meta_ads_expert")
            self.assertEqual(items[0].play_count, 115000)
            self.assertEqual(items[0].like_count, 6800)
            self.assertEqual(items[0].comment_count, 420)
            self.assertEqual(items[0].share_count, 2100)
            self.assertIsNone(next_cursor)
            self.assertFalse(items[0].is_mock)

    def test_fetch_reels_by_creator_validation(self):
        """Verify empty creator handle is rejected and leading '@' is stripped."""
        client = SocialFetchClient(self.config, use_mock=True)
        with self.assertRaises(ValueError):
            client.fetch_reels_by_creator("")
        with self.assertRaises(ValueError):
            client.fetch_reels_by_creator("   ")

        # Calling with leading '@' should work cleanly
        items, profile, _ = client.fetch_reels_by_creator("@alex_growth_media", limit=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(profile.get("handle"), "alex_growth_media")

    # =========================================================================
    # Engagement & Popularity Scoring Tests (Stage 4)
    # =========================================================================

    def test_scoring_rates_and_formulas(self):
        """Verify like rate, comment rate, share rate, and overall rate formulas."""
        engine = EngagementScoringEngine()
        reel = ReelItem(
            reel_id="test_reel_101",
            shortcode="C101",
            url="https://instagram.com/reel/C101/",
            caption="Scale Meta Ads profitably with Advantage+ #metaads",
            author_username="ad_master",
            play_count=100000,
            like_count=5000,     # 5.0%
            comment_count=400,   # 0.4%
            share_count=1200,    # 1.2%
            hashtags=["metaads"],
            published_at="2026-11-20T12:00:00Z"
        )
        rates = engine.calculate_rates(reel)
        self.assertEqual(rates.like_rate, 5.0)
        self.assertEqual(rates.comment_rate, 0.4)
        self.assertEqual(rates.share_rate, 1.2)
        # weighted interactions: 5000*1.0 + 400*2.5 + 1200*4.0 = 5000 + 1000 + 4800 = 10800
        # overall rate: (10800 / 100000) * 100 = 10.8%
        self.assertEqual(rates.overall_rate, 10.8)

    def test_scoring_missing_metrics_handling(self):
        """Ensure missing metrics remain None and are not treated as zero."""
        engine = EngagementScoringEngine()

        # Case 1: Views is None -> all rates and engagement score must be None
        reel_no_views = ReelItem(
            reel_id="test_reel_no_views",
            shortcode="C_NOV",
            url="https://instagram.com/reel/C_NOV/",
            caption="Test caption without views",
            author_username="creator_a",
            play_count=None,
            like_count=150,
            comment_count=20,
            share_count=None
        )
        rates = engine.calculate_rates(reel_no_views)
        self.assertIsNone(rates.like_rate)
        self.assertIsNone(rates.comment_rate)
        self.assertIsNone(rates.share_rate)
        self.assertIsNone(rates.overall_rate)
        self.assertIsNone(engine.calculate_engagement_score(rates))

        # Case 2: Views is 0 -> safely handled without ZeroDivisionError
        reel_zero_views = ReelItem(
            reel_id="test_reel_zero_views",
            shortcode="C_ZERO",
            url="https://instagram.com/reel/C_ZERO/",
            caption="Zero views test",
            author_username="creator_b",
            play_count=0,
            like_count=0
        )
        rates_zero = engine.calculate_rates(reel_zero_views)
        self.assertIsNone(rates_zero.like_rate)
        self.assertIsNone(rates_zero.overall_rate)

        # Case 3: Missing shares & comments -> like rate is computed, share & comment rates are None
        reel_partial = ReelItem(
            reel_id="test_reel_partial",
            shortcode="C_PARTIAL",
            url="https://instagram.com/reel/C_PARTIAL/",
            caption="Partial metrics test",
            author_username="creator_c",
            play_count=50000,
            like_count=2500,
            comment_count=None,
            share_count=None
        )
        rates_partial = engine.calculate_rates(reel_partial)
        self.assertEqual(rates_partial.like_rate, 5.0)
        self.assertIsNone(rates_partial.comment_rate)
        self.assertIsNone(rates_partial.share_rate)
        self.assertIsNotNone(rates_partial.overall_rate)

        # Case 4: All volume metrics None -> popularity score is None
        reel_empty = ReelItem(
            reel_id="test_empty",
            shortcode="C_EMPTY",
            url="https://instagram.com/reel/C_EMPTY/",
            caption="Empty metrics",
            author_username="creator_d",
            play_count=None,
            like_count=None,
            comment_count=None,
            share_count=None
        )
        self.assertIsNone(engine.calculate_popularity_score(reel_empty))

    def test_scoring_recency_decay(self):
        """Verify exponential half-life decay of recency score and missing timestamp handling."""
        engine = EngagementScoringEngine()
        from datetime import datetime, timezone, timedelta

        ref_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        # 0 days old -> ~100.0
        score_0, age_0 = engine.calculate_recency_score("2026-11-24T12:00:00Z", reference_time=ref_time)
        self.assertEqual(score_0, 100.0)
        self.assertEqual(age_0, 0.0)

        # 7 days old (half-life = 7 days) -> ~50.0
        score_7, age_7 = engine.calculate_recency_score("2026-11-17T12:00:00Z", reference_time=ref_time)
        self.assertAlmostEqual(score_7, 50.0, places=1)
        self.assertAlmostEqual(age_7, 7.0, places=1)

        # 14 days old -> ~25.0
        score_14, age_14 = engine.calculate_recency_score("2026-11-10T12:00:00Z", reference_time=ref_time)
        self.assertAlmostEqual(score_14, 25.0, places=1)

        # Missing or invalid timestamp -> None
        score_none, age_none = engine.calculate_recency_score(None)
        self.assertIsNone(score_none)
        self.assertIsNone(age_none)

        score_inv, age_inv = engine.calculate_recency_score("invalid-date-string")
        self.assertIsNone(score_inv)
        self.assertIsNone(age_inv)

    def test_scoring_creator_performance_benchmark(self):
        """Verify creator benchmark requires at least 3 reels and does not invent data."""
        engine = EngagementScoringEngine()

        # Creator with only 2 reels (insufficient data)
        reel_a1 = ReelItem(
            reel_id="r_a1", shortcode="CA1", url="url", caption="caption", author_username="creator_solo",
            play_count=10000, like_count=500
        )
        reel_a2 = ReelItem(
            reel_id="r_a2", shortcode="CA2", url="url", caption="caption", author_username="creator_solo",
            play_count=20000, like_count=1000
        )

        rates_a1 = engine.calculate_rates(reel_a1)
        bench_a1 = engine.calculate_creator_benchmark(reel_a1, [reel_a1, reel_a2], rates_a1)
        self.assertFalse(bench_a1.has_sufficient_data)
        self.assertEqual(bench_a1.creator_reel_count, 2)
        self.assertIsNone(bench_a1.views_multiplier)
        self.assertIsNone(bench_a1.performance_score)

        # Creator with 3 reels (sufficient data)
        reel_a3 = ReelItem(
            reel_id="r_a3", shortcode="CA3", url="url", caption="caption", author_username="creator_solo",
            play_count=30000, like_count=3000  # 10% engagement rate
        )
        all_creator_reels = [reel_a1, reel_a2, reel_a3]
        rates_a3 = engine.calculate_rates(reel_a3)
        bench_a3 = engine.calculate_creator_benchmark(reel_a3, all_creator_reels, rates_a3)
        self.assertTrue(bench_a3.has_sufficient_data)
        self.assertEqual(bench_a3.creator_reel_count, 3)
        self.assertIsNotNone(bench_a3.creator_avg_views)
        self.assertGreater(bench_a3.views_multiplier, 1.0)
        self.assertIsNotNone(bench_a3.performance_score)

    def test_scoring_deduplication(self):
        """Verify duplicate reels by reel_id or shortcode are cleanly removed."""
        engine = EngagementScoringEngine()
        reels = [
            ReelItem(reel_id="id_1", shortcode="CODE1", url="u1", caption="c1", author_username="auth1"),
            ReelItem(reel_id="id_1", shortcode="CODE1_DUP", url="u1", caption="c1 duplicate id", author_username="auth1"),
            ReelItem(reel_id="id_2", shortcode="CODE1", url="u2", caption="c2 duplicate code", author_username="auth2"),
            ReelItem(reel_id="id_3", shortcode="CODE3", url="u3", caption="c3 unique", author_username="auth3"),
        ]
        deduped = engine.deduplicate_reels(reels)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0].reel_id, "id_1")
        self.assertEqual(deduped[1].reel_id, "id_3")

    def test_scoring_three_separate_rankings(self):
        """Verify the three distinct rankings: Most Popular, Best Engagement, Rising Content."""
        engine = EngagementScoringEngine()
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        # Reel A: Massive reach, moderate engagement, older (30 days ago)
        reel_mega = ReelItem(
            reel_id="r_mega", shortcode="C_MEGA", url="u1",
            caption="Huge viral Meta Ads breakdown #metaads #businessgrowth",
            author_username="guru",
            play_count=2000000,
            like_count=120000,
            comment_count=8000,
            share_count=25000,
            published_at=(now - timedelta(days=30)).isoformat()
        )

        # Reel B: Niche hit with incredible engagement rate (35% overall rate), medium reach, 10 days ago
        reel_eng = ReelItem(
            reel_id="r_eng", shortcode="C_ENG", url="u2",
            caption="Actionable B2B lead generation script framework #leadgeneration",
            author_username="b2b_expert",
            play_count=50000,
            like_count=7000,   # 14%
            comment_count=1500, # 3%
            share_count=4000,  # 8%
            published_at=(now - timedelta(days=10)).isoformat()
        )

        # Reel C: Brand new fresh reel (2 hours ago), high initial momentum
        reel_rising = ReelItem(
            reel_id="r_rising", shortcode="C_RISING", url="u3",
            caption="Breaking algorithm update for Instagram marketing in 2026 #instagrammarketing",
            author_username="insta_insider",
            play_count=150000,
            like_count=16000,
            comment_count=1200,
            share_count=3500,
            published_at=(now - timedelta(hours=2)).isoformat()
        )

        rankings = engine.rank_reels([reel_mega, reel_eng, reel_rising], reference_time=now)

        # Most Popular: Mega reach should lead
        self.assertEqual(rankings["most_popular"][0].reel_id, "r_mega")

        # Best Engagement: High interaction density should lead
        self.assertEqual(rankings["best_engagement"][0].reel_id, "r_eng")

        # Rising Content: High recency + strong momentum should lead
        self.assertEqual(rankings["rising_content"][0].reel_id, "r_rising")

    # =========================================================================
    # Trending Detection Engine Tests (Stage 5)
    # =========================================================================

    def test_trending_momentum_vs_historical_popularity(self):
        """Distinguish historical popularity from recent momentum: high views alone must not make an old reel trending."""
        engine = TrendingDetectionEngine()
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        # Reel A: Massive lifetime views (3M) but 45 days old -> Not currently trending
        old_mega = ReelItem(
            reel_id="old_mega", shortcode="COLD", url="u1",
            caption="Old classic breakdown #metaads", author_username="creator_old",
            play_count=3000000, like_count=180000, comment_count=12000, share_count=40000,
            published_at=(now - timedelta(days=45)).isoformat()
        )

        # Reel B: Fresh reel (1.5 days old), 250k views, accelerating momentum -> Trending & Rising
        fresh_rising = ReelItem(
            reel_id="fresh_rising", shortcode="CFRESH", url="u2",
            caption="New algorithm exploit for Meta Ads 2026 #metaads #growth",
            author_username="creator_fresh",
            play_count=250000, like_count=22000, comment_count=1800, share_count=6500,
            published_at=(now - timedelta(days=1.5)).isoformat()
        )

        res_old = engine.evaluate_reel(old_mega, reference_time=now)
        res_fresh = engine.evaluate_reel(fresh_rising, reference_time=now)

        # Assert old reel is Popular but NOT Rising or Trending
        self.assertTrue(res_old.is_popular)
        self.assertFalse(res_old.is_rising)
        self.assertFalse(res_old.is_trending)
        self.assertLessEqual(res_old.trending_score, 60.0)

        # Assert fresh reel has higher trending score and is classified as Rising & Trending
        self.assertTrue(res_fresh.is_rising)
        self.assertTrue(res_fresh.is_trending)
        self.assertGreater(res_fresh.trending_score, res_old.trending_score)

    def test_trending_creator_outperformance_detection(self):
        """Verify reels exceeding creator historical baseline by 1.75x+ are tagged as creator outperformers."""
        engine = TrendingDetectionEngine()
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        # Creator with baseline average ~20k views
        r1 = ReelItem(reel_id="c_r1", shortcode="C1", url="", caption="tip 1", author_username="scaler", play_count=18000, like_count=900, published_at=(now - timedelta(days=5)).isoformat())
        r2 = ReelItem(reel_id="c_r2", shortcode="C2", url="", caption="tip 2", author_username="scaler", play_count=22000, like_count=1100, published_at=(now - timedelta(days=4)).isoformat())
        # Outperformer reel: 85k views (>3x average)
        r_breakout = ReelItem(reel_id="c_breakout", shortcode="C3", url="", caption="Breakthrough lead gen framework #leadgeneration", author_username="scaler", play_count=85000, like_count=6800, comment_count=520, share_count=1800, published_at=(now - timedelta(days=1)).isoformat())

        all_reels = [r1, r2, r_breakout]
        res = engine.evaluate_reel(r_breakout, all_reels=all_reels, reference_time=now)

        self.assertTrue(res.is_creator_outperformer)
        self.assertIn("Outperformed creator baseline", res.explanation)

    def test_trending_cross_creator_emerging_topics(self):
        """Verify emerging topics cluster across independent creators and do not count duplicates or single creators."""
        engine = TrendingDetectionEngine()

        # Topic: 'crmautomation' shared across 3 independent creators
        r1 = ReelItem(reel_id="top_1", shortcode="T1", url="", caption="Scale faster with #crmautomation and AI", author_username="creator_alpha")
        r2 = ReelItem(reel_id="top_2", shortcode="T2", url="", caption="How we set up #crmautomation for agencies", author_username="creator_beta")
        r3 = ReelItem(reel_id="top_3", shortcode="T3", url="", caption="Why every B2B needs #crmautomation workflows", author_username="creator_gamma")

        # Same creator posting about 'solopreneur' 3 times -> MUST NOT count as cross-creator emerging topic
        r_solo1 = ReelItem(reel_id="s1", shortcode="S1", url="", caption="#solopreneur tip 1", author_username="solo_guy")
        r_solo2 = ReelItem(reel_id="s2", shortcode="S2", url="", caption="#solopreneur tip 2", author_username="solo_guy")
        r_solo3 = ReelItem(reel_id="s3", shortcode="S3", url="", caption="#solopreneur tip 3", author_username="solo_guy")

        reels = [r1, r2, r3, r_solo1, r_solo2, r_solo3]
        report = engine.analyze_dataset(reels)

        topic_keys = [t.topic_key for t in report.emerging_topics]

        # 'crmautomation' must be detected with 3 independent creators
        self.assertIn("crmautomation", topic_keys)
        crm_cluster = next(t for t in report.emerging_topics if t.topic_key == "crmautomation")
        self.assertEqual(crm_cluster.independent_creator_count, 3)
        self.assertEqual(len(crm_cluster.creators), 3)

        # 'solopreneur' was only posted by 1 creator (solo_guy), so it must be excluded
        self.assertNotIn("solopreneur", topic_keys)

    def test_trending_insufficient_data_handling(self):
        """Verify graceful handling when timestamps or all metrics are missing without crashing or inventing stats."""
        engine = TrendingDetectionEngine()

        # Case 1: Missing publish timestamp
        reel_no_date = ReelItem(
            reel_id="nodate", shortcode="ND1", url="",
            caption="Testing lead generation #leadgen",
            author_username="auth1",
            play_count=50000, like_count=2000,
            published_at=None
        )
        res_nodate = engine.evaluate_reel(reel_no_date)
        self.assertFalse(res_nodate.has_sufficient_data)
        self.assertIn("Publication date unknown", res_nodate.explanation)
        self.assertIsNone(res_nodate.recency_score)

        # Case 2: All metric counts missing
        reel_empty = ReelItem(
            reel_id="empty", shortcode="E1", url="",
            caption="Empty reel", author_username="auth2",
            play_count=None, like_count=None, comment_count=None, share_count=None,
            published_at=None
        )
        res_empty = engine.evaluate_reel(reel_empty)
        self.assertFalse(res_empty.has_sufficient_data)
        self.assertEqual(res_empty.trending_score, 0.0)
        self.assertIn("Insufficient data", res_empty.explanation)

    def test_trending_niche_trends_partitioning(self):
        """Verify analyze_dataset cleanly partitions reels across AdSync's 8 core marketing categories."""
        engine = TrendingDetectionEngine()

        reels = [
            ReelItem(reel_id="cat_1", shortcode="C1", url="", caption="Scale Meta Ads #metaads #roas", author_username="a1", play_count=10000),
            ReelItem(reel_id="cat_2", shortcode="C2", url="", caption="Inbound lead generation funnels #leadgen", author_username="a2", play_count=20000),
            ReelItem(reel_id="cat_3", shortcode="C3", url="", caption="Luxury real estate home walkthrough #luxuryrealestate #propertyvideo", author_username="a3", play_count=30000),
            ReelItem(reel_id="cat_4", shortcode="C4", url="", caption="Unrelated funny cooking recipe video", author_username="a4", play_count=5000),
        ]

        report = engine.analyze_dataset(reels)
        self.assertEqual(len(report.trending_reels), 4)

        # Meta Ads category has cat_1
        self.assertIn("Meta Ads", report.niche_trends)
        self.assertTrue(any(r.reel_id == "cat_1" for r in report.niche_trends["Meta Ads"]))

        # Lead Generation category has cat_2
        self.assertIn("Lead Generation", report.niche_trends)
        self.assertTrue(any(r.reel_id == "cat_2" for r in report.niche_trends["Lead Generation"]))

        # Real Estate Marketing category has cat_3
        self.assertIn("Real Estate Marketing", report.niche_trends)
        self.assertTrue(any(r.reel_id == "cat_3" for r in report.niche_trends["Real Estate Marketing"]))

        # Irrelevant cooking video falls into Other
        self.assertTrue(any(r.reel_id == "cat_4" for r in report.niche_trends["Other / Irrelevant"]))

    # =========================================================================
    # Competitor Intelligence Engine Tests (Stage 6)
    # =========================================================================

    def test_competitor_crud_and_category_validation(self):
        """Verify competitor add, edit, list, remove, and category enforcement."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_comp.db"
            repo = DatabaseRepository(db_path)
            engine = CompetitorIntelligenceEngine(db_repo=repo)

            # Invalid category rejection
            with self.assertRaises(ValueError):
                engine.add_competitor("bad_agency", "Fashion & Beauty")

            # Valid category addition
            comp1 = engine.add_competitor("@ad_agency_pro", "Meta Ads Specialists", notes="Top scale competitor")
            self.assertEqual(comp1.handle, "ad_agency_pro")
            self.assertEqual(comp1.category, "Meta Ads Specialists")

            comp2 = engine.add_competitor("lead_funnels_io", "Lead Generation Experts")
            self.assertEqual(comp2.handle, "lead_funnels_io")

            # Listing by category
            meta_comps = engine.list_competitors(category="Meta Ads Specialists")
            self.assertEqual(len(meta_comps), 1)
            self.assertEqual(meta_comps[0].handle, "ad_agency_pro")

            # Update category
            engine.update_competitor("ad_agency_pro", category="Digital Marketing Agencies", notes="Pivoted focus")
            updated = engine.get_competitor("ad_agency_pro")
            self.assertEqual(updated.category, "Digital Marketing Agencies")
            self.assertEqual(updated.notes, "Pivoted focus")

            # Removal
            removed = engine.remove_competitor("ad_agency_pro")
            self.assertTrue(removed)
            self.assertIsNone(engine.get_competitor("ad_agency_pro"))

    def test_competitor_sync_and_snapshot_tracking(self):
        """Verify profile synchronization, deduplication, and time-series snapshots."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_comp_sync.db"
            repo = DatabaseRepository(db_path)
            client = SocialFetchClient(self.config, use_mock=True)
            engine = CompetitorIntelligenceEngine(db_repo=repo, client=client)

            # Register competitor
            engine.add_competitor("alex_growth_media", "Meta Ads Specialists")

            # First sync
            prof1, reels1 = engine.sync_competitor_profile("alex_growth_media", limit=5)
            self.assertIsNotNone(prof1.last_fetched_at)
            self.assertGreater(len(reels1), 0)

            # Verify snapshot logged
            first_reel_id = reels1[0].reel_id
            snaps = repo.get_reel_snapshots(first_reel_id)
            self.assertEqual(len(snaps), 1)
            self.assertEqual(snaps[0].handle, "alex_growth_media")

            # Second sync (time-series tracking)
            prof2, reels2 = engine.sync_competitor_profile("alex_growth_media", limit=5)
            snaps2 = repo.get_reel_snapshots(first_reel_id)
            self.assertEqual(len(snaps2), 2)
            # Database should not duplicate the reel record
            reels_in_db = repo.get_reels()
            self.assertEqual(len(reels_in_db), len(reels1))

    def test_competitor_private_profile_and_missing_data_safety(self):
        """Verify handling of private profiles or empty media grids safely without crashing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_comp_priv.db"
            repo = DatabaseRepository(db_path)

            mock_client = MagicMock()
            # Simulate a private account where recentMedia is null/empty
            mock_client.fetch_reels_by_creator.return_value = (
                [],
                {
                    "handle": "private_agency",
                    "displayName": "Private Growth Agency",
                    "bio": "Private client account.",
                    "verified": False,
                    "privateAccount": True,
                    "counts": {"posts": 50, "followers": 12000, "following": 150}
                },
                None
            )

            engine = CompetitorIntelligenceEngine(db_repo=repo, client=mock_client)
            engine.add_competitor("private_agency", "Branding Agencies")

            prof, reels = engine.sync_competitor_profile("private_agency")
            self.assertTrue(prof.is_private)
            self.assertEqual(len(reels), 0)

            summary = engine.summarize_competitor("private_agency")
            self.assertEqual(summary.reels_tracked, 0)
            self.assertTrue(summary.is_private)
            self.assertIsNone(summary.avg_views_per_reel)
            self.assertEqual(len(summary.top_reels), 0)

    def test_competitor_summary_and_cross_comparison(self):
        """Verify competitor analytics, top reels, recurring topics, and leaderboard rankings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_comp_summary.db"
            repo = DatabaseRepository(db_path)
            engine = CompetitorIntelligenceEngine(db_repo=repo)

            # Seed 2 competitors
            engine.add_competitor("competitor_one", "Lead Generation Experts")
            engine.add_competitor("competitor_two", "Lead Generation Experts")

            # Seed reels for competitor_one (High reach)
            r1 = ReelItem(reel_id="c1_1", shortcode="CODE1", url="u1", caption="Scale lead generation with #crmautomation and #funnels", author_username="competitor_one", play_count=100000, like_count=8000, comment_count=500, share_count=1200)
            r2 = ReelItem(reel_id="c1_2", shortcode="CODE2", url="u2", caption="How to get booked calls with #crmautomation outreach", author_username="competitor_one", play_count=120000, like_count=9500, comment_count=600, share_count=1500)
            repo.save_reels([r1, r2])

            # Seed reels for competitor_two (High engagement density, lower views)
            r3 = ReelItem(reel_id="c2_1", shortcode="CODE3", url="u3", caption="Stop boosting posts for #leadgeneration", author_username="competitor_two", play_count=20000, like_count=4000, comment_count=400, share_count=1000)
            repo.save_reels([r3])

            # Summarize competitor_one
            summary1 = engine.summarize_competitor("competitor_one")
            self.assertEqual(summary1.reels_tracked, 2)
            self.assertEqual(summary1.avg_views_per_reel, 110000.0)
            self.assertGreater(len(summary1.top_reels), 0)
            # Keyword crmautomation should appear in recurring topics
            recurring_kws = [t["keyword"] for t in summary1.recurring_topics]
            self.assertIn("crmautomation", recurring_kws)

            # Compare competitors
            report = engine.compare_competitors(category="Lead Generation Experts")
            self.assertEqual(report.total_competitors, 2)
            # competitor_one has higher reach
            self.assertEqual(report.rankings_by_reach[0], "competitor_one")
            # competitor_two has higher engagement rate (likes/views = 20%)
            self.assertEqual(report.rankings_by_engagement[0], "competitor_two")

    # =========================================================================
    # Hook & Format Intelligence Tests (Stage 7)
    # =========================================================================

    def test_hook_classification_archetypes(self):
        """Verify accurate classification of opening hooks across psychological archetypes."""
        engine = HookFormatIntelligenceEngine()

        test_cases = [
            ("Stop boosting posts if your goal is real revenue in 2026.", "Contrarian / Myth-Busting"),
            ("The secret reason why Meta ad costs doubled quietly this month.", "Curiosity Gap"),
            ("5 steps to set up automated client onboarding in 10 minutes.", "List-Based"),
            ("How to build a high-ticket B2B outbound engine from scratch.", "Educational / How-To"),
            ("Why are 90% of agency owners burning out before reaching $50k/mo?", "Question-Based"),
            ("Tired of struggling with dry sales pipelines and low response rates?", "Problem-Solution"),
            ("How our client went from 0 to $120,000 in tracked consultation revenue.", "Social Proof"),
            ("In 2020, we were losing $8,000 every single week on broken campaigns.", "Storytelling"),
            ("Don't miss out before Meta bans this targeting workaround forever.", "Fear of Missing Out"),
            ("This single prompt will guarantee your highest converting ad script ever.", "Bold Claim"),
        ]

        for hook_text, expected_cat in test_cases:
            hook_detail = engine.classify_hook(hook_text, is_extracted=True)
            self.assertEqual(hook_detail.category, expected_cat, f"Failed for hook: {hook_text}")
            self.assertTrue(hook_detail.is_extracted)
            self.assertGreater(hook_detail.confidence, 0.70)

    def test_format_classification_and_uncertainty(self):
        """Verify video format classification and proper handling of uncertain/mixed formats."""
        engine = HookFormatIntelligenceEngine()

        # Screen recording
        r_screen = ReelItem(reel_id="f1", shortcode="S1", url="", caption="Open Ads Manager and configure this webhook in your dashboard.", author_username="a")
        fmt_screen = engine.classify_format(r_screen)
        self.assertEqual(fmt_screen.format_name, "Screen Recording")
        self.assertFalse(fmt_screen.is_uncertain)

        # Cinematic B-roll
        r_broll = ReelItem(reel_id="f2", shortcode="S2", url="", caption="Luxury real estate home walkthrough in Miami neighborhood.", author_username="b")
        fmt_broll = engine.classify_format(r_broll)
        self.assertEqual(fmt_broll.format_name, "Cinematic B-Roll")

        # Uncertain / Mixed format
        r_uncertain = ReelItem(reel_id="f3", shortcode="S3", url="", caption="Just thinking about life and success.", author_username="c")
        fmt_uncertain = engine.classify_format(r_uncertain)
        self.assertEqual(fmt_uncertain.format_name, "Mixed Format")
        self.assertTrue(fmt_uncertain.is_uncertain)

    def test_content_structure_mapping_and_no_fabrication(self):
        """Verify structure analysis maps elements accurately and never fabricates missing sections."""
        engine = HookFormatIntelligenceEngine()

        # Full structured caption
        full_caption = (
            "Stop boosting posts on Instagram.\n\n"
            "The mistake is optimizing for vanity likes instead of tracked leads.\n"
            "The reason this fails is that Meta targets casual clickers.\n"
            "Step 1: Open Ads Manager.\n"
            "Step 2: Pick Leads objective.\n"
            "For example, our client went from 12 leads to 84.\n"
            "Now you can scale profitably.\n"
            "Comment 'ADS' for the full campaign guide."
        )
        struct = engine.analyze_structure(full_caption)
        self.assertTrue(struct.has_hook)
        self.assertTrue(struct.has_problem)
        self.assertTrue(struct.has_explanation)
        self.assertTrue(struct.has_demonstration)
        self.assertTrue(struct.has_proof)
        self.assertTrue(struct.has_payoff)
        self.assertTrue(struct.has_cta)
        self.assertIn("Hook -> Problem -> Explanation", struct.structure_flow)
        self.assertEqual(struct.completeness_score, 100.0)

        # Minimal / partial structure (never fabricates missing demonstration or proof)
        partial_caption = "Why are you struggling with sales? Here is why it happens."
        struct_part = engine.analyze_structure(partial_caption)
        self.assertTrue(struct_part.has_hook)
        self.assertTrue(struct_part.has_problem)
        self.assertTrue(struct_part.has_explanation)
        self.assertFalse(struct_part.has_demonstration)
        self.assertFalse(struct_part.has_proof)
        self.assertFalse(struct_part.has_cta)
        self.assertLess(struct_part.completeness_score, 50.0)

    def test_cta_detection_patterns(self):
        """Verify accurate identification of specific call-to-action patterns."""
        engine = HookFormatIntelligenceEngine()

        self.assertEqual(engine.analyze_cta("Comment 'LEAD' below.").cta_type, "Comment")
        self.assertEqual(engine.analyze_cta("DM me 'SCALE' for the blueprint.").cta_type, "DM")
        self.assertEqual(engine.analyze_cta("Save this for your next video shoot!").cta_type, "Save")
        self.assertEqual(engine.analyze_cta("Share this with your business partner.").cta_type, "Share")
        self.assertEqual(engine.analyze_cta("Follow for daily marketing tips.").cta_type, "Follow")
        self.assertEqual(engine.analyze_cta("Click the link in bio to register.").cta_type, "Click Link")
        self.assertEqual(engine.analyze_cta("Book a call with our team today.").cta_type, "Contact / Enquiry")
        self.assertEqual(engine.analyze_cta("Just enjoying the weekend.").cta_type, "No Clear CTA")

    def test_missing_data_safety_in_hook_analysis(self):
        """Verify missing captions and empty text return honest placeholders without fabricating audio transcripts."""
        engine = HookFormatIntelligenceEngine()

        reel_no_text = ReelItem(reel_id="m1", shortcode="M1", url="", caption="", author_username="a")
        eval_res = engine.evaluate_reel(reel_no_text)

        self.assertFalse(eval_res.has_sufficient_text)
        self.assertFalse(eval_res.hook.is_extracted)
        self.assertEqual(eval_res.hook.category, "Unknown / No Text")
        self.assertEqual(eval_res.structure.completeness_score, 0.0)
        self.assertEqual(eval_res.cta.cta_type, "No Clear CTA")

    def test_pattern_performance_reporting_and_correlation_disclaimer(self):
        """Verify performance intelligence aggregates patterns and includes correlation disclaimer."""
        engine = HookFormatIntelligenceEngine()

        r1 = ReelItem(reel_id="p1", shortcode="P1", url="", caption="Stop boosting posts! Comment 'ADS'.", author_username="ad_guru", play_count=100000, like_count=8000, comment_count=900, share_count=2000)
        r2 = ReelItem(reel_id="p2", shortcode="P2", url="", caption="5 tools to automate your CRM workflow. Save this checklist.", author_username="saas_scaler", play_count=60000, like_count=5000, comment_count=300, share_count=1500)

        report = engine.analyze_patterns_and_performance([r1, r2])

        self.assertEqual(report.total_reels_analyzed, 2)
        self.assertGreater(len(report.most_common_hooks), 0)
        self.assertGreater(len(report.best_performing_hooks), 0)
        self.assertGreater(len(report.cta_performance), 0)
        self.assertIn("Correlation Notice", report.correlation_disclaimer)
        self.assertIn("ad_guru", report.competitor_pattern_differences)

    def test_adsync_niche_recommendations(self):
        """Verify niche content recommendations deliver original blueprints across all 8 verticals."""
        engine = HookFormatIntelligenceEngine()

        for niche in ["Meta Ads", "Lead Generation", "Marketing Automation", "Instagram Marketing", "Real Estate Marketing"]:
            rec = engine.get_niche_recommendations(niche)
            self.assertEqual(rec.niche, niche)
            self.assertGreater(len(rec.recommended_hook_categories), 0)
            self.assertGreater(len(rec.recommended_formats), 0)
            self.assertGreater(len(rec.sample_original_hook_templates), 0)
            self.assertTrue(len(rec.recommended_cta_strategy) > 0)
            self.assertTrue(len(rec.strategic_rationale) > 0)

    # =========================================================================
    # AI Creative Director Tests (Stage 8)
    # =========================================================================

    def test_creative_director_mode_b_user_prompt_parsing(self):
        """Verify Mode B parses natural language briefs, durations, audiences, and tones."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            director = AICreativeDirector(output_dir=Path(tmp_dir))
            prompt = (
                "Create a 45-second Reel explaining why businesses get Instagram views "
                "but no customers. Target small business owners. Make it professional and engaging."
            )
            parsed = director.parse_user_prompt(prompt)

            self.assertEqual(parsed["duration"], 45)
            self.assertEqual(parsed["target_category"], "Instagram Marketing")
            self.assertEqual(parsed["target_audience"], "Small Business Owners & Founders")
            self.assertEqual(parsed["tone"], "Professional & Engaging")
            self.assertIn("businesses get Instagram views but no customers", parsed["topic"])

    def test_creative_director_mode_b_brief_and_script_generation(self):
        """Verify Mode B full brief generation, script calibration, and scene plans."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            director = AICreativeDirector(output_dir=Path(tmp_dir))
            prompt = "Create a 30-second Reel explaining Meta Ads Advantage+ campaigns for agency founders."
            brief = director.create_brief_from_user_prompt(
                prompt,
                voice="am_michael",
                music="tension",
                style="deep-dive"
            )

            self.assertEqual(brief.creation_mode, "mode_b_user_topic")
            self.assertEqual(brief.decisions.video_style, "deep-dive")
            self.assertEqual(brief.decisions.voice, "am_michael")
            self.assertEqual(brief.decisions.music, "tension")
            self.assertEqual(brief.decisions.target_duration, 30)
            self.assertGreater(len(brief.script_lines), 0)
            self.assertGreater(len(brief.scene_plans), 0)

            # Check script line contract (text & caps)
            for line in brief.script_lines:
                self.assertIn("text", line)
                self.assertIn("caps", line)
                self.assertTrue(len(line["text"]) > 0)
                self.assertTrue(len(line["caps"]) > 0)

            # Check scene plan contract
            for scene in brief.scene_plans:
                self.assertGreater(scene.scene_number, 0)
                self.assertTrue(len(scene.narration_text) > 0)
                self.assertTrue(len(scene.visual_description) > 0)
                self.assertGreater(scene.estimated_duration, 0.0)

            # Check duration calibration
            self.assertAlmostEqual(brief.decisions.estimated_duration, 30.0, delta=12.0)

    def test_creative_director_mode_a_intelligence_driven(self):
        """Verify Mode A autonomously generates concepts from marketing intelligence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            director = AICreativeDirector(output_dir=Path(tmp_dir))
            brief = director.create_brief_from_intelligence(
                category="Lead Generation",
                duration=45
            )

            self.assertEqual(brief.creation_mode, "mode_a_intelligence")
            self.assertEqual(brief.decisions.target_category, "Lead Generation")
            self.assertEqual(brief.decisions.target_duration, 45)
            self.assertGreater(len(brief.script_lines), 0)
            self.assertTrue(len(brief.decisions.call_to_action) > 0)

    def test_creative_director_faceless_shorts_rendering_config(self):
        """Verify rendering_config matches the exact input contract of Faceless Shorts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            director = AICreativeDirector(output_dir=out_path)
            brief = director.create_brief_from_user_prompt(
                "30s video on marketing automation",
                style="inside-out",
                voice="af_bella",
                music="bed"
            )

            cfg = brief.rendering_config
            self.assertIn("title", cfg)
            self.assertEqual(cfg["style"], "inside-out")
            self.assertEqual(cfg["voice"], "af_bella")
            self.assertEqual(cfg["music"], "bed")
            self.assertIn("lines", cfg)
            self.assertIn("lead", cfg)
            self.assertIn("outro", cfg)
            self.assertIn("gap", cfg)
            self.assertIn("sources", cfg)

            # Check that files were written on disk
            self.assertIsNotNone(brief.project_directory)
            proj_p = Path(brief.project_directory)
            self.assertTrue((proj_p / "script.json").is_file())
            self.assertTrue((proj_p / "creative_brief.json").is_file())

            # Read back script.json to verify valid JSON content
            with open(proj_p / "script.json", "r", encoding="utf-8") as f:
                loaded_script = json.load(f)
            self.assertEqual(loaded_script["voice"], "af_bella")
            self.assertEqual(loaded_script["style"], "inside-out")

    def test_creative_director_invalid_and_missing_inputs(self):
        """Verify fallback to defaults on invalid style/voice or empty prompt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            director = AICreativeDirector(output_dir=Path(tmp_dir))

            # Empty prompt raises ValueError
            with self.assertRaises(ValueError):
                director.create_brief_from_user_prompt("")
            with self.assertRaises(ValueError):
                director.create_brief_from_user_prompt("   ")

            # Unsupported style, voice, or music falls back to sensible defaults
            decision = director.make_creative_decisions(
                topic="Test Invalid Inputs",
                category="Branding",
                target_audience="General",
                requested_style="unsupported_3d_engine",
                requested_voice="fake_celebrity_voice",
                requested_music="pirated_pop_track"
            )
            self.assertEqual(decision.video_style, "stick-story")
            self.assertEqual(decision.voice, "am_michael")
            self.assertEqual(decision.music, "bed")


if __name__ == "__main__":
    unittest.main()
