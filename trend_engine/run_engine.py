#!/usr/bin/env python3
"""Unified CLI entrypoint for AdSync Trend Engine (Phase 2).

Commands:
  python trend_engine/run_engine.py               # Runs complete pipeline in mock mode (default)
  python trend_engine/run_engine.py --mock        # Explicit mock mode run
  python trend_engine/run_engine.py --probe       # Validates configuration and credentials safely
  python trend_engine/run_engine.py --stats       # Displays database trend stats
  python trend_engine/run_engine.py --report      # Re-generates daily report from database
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from trend_engine.config import get_config, mask_key
from trend_engine.providers.social_fetch import SocialFetchClient
from trend_engine.providers.base import (
    TrendProviderError,
    PaymentRequiredError,
    AuthenticationError,
    RateLimitError,
    ForbiddenError,
    ProviderServerError,
)
from trend_engine.storage.database import DatabaseRepository
from trend_engine.analysis.hook_extractor import analyze_reel
from trend_engine.analysis.idea_generator import generate_batch_ideas
from trend_engine.reporting.daily_report import DailyReportGenerator


def run_pipeline(use_mock: bool = True) -> int:
    """Executes the complete end-to-end ingestion, analysis, and reporting pipeline."""
    config = get_config()
    if not use_mock and config.force_mock_mode:
        print("\n[SAFETY LOCK ACTIVE] FORCE_MOCK_MODE=1 is set in .env.")
        print("                     Live network requests are safely locked to prevent credit expenditure.")
        print("                     To permit live external requests, set FORCE_MOCK_MODE=0 in trend_engine/.env.")
        use_mock = True

    db = DatabaseRepository(config.db_path)
    client = SocialFetchClient(config, use_mock=use_mock)

    mode_label = "MOCK / TEST FIXTURE MODE" if use_mock else "LIVE API MODE"
    print("=" * 75)
    print(f" AdSync Autonomous Social Media Engine — Trend Pipeline ({mode_label})")
    print("=" * 75)

    if use_mock:
        print("\n[!] NOTICE: Running with MOCK DATA. Real API calls are disabled.")
        print("    Data is sourced from realistic test fixtures to avoid spending credits.\n")
    else:
        print("\n[!] CAUTION: LIVE API MODE. Attempting live Social Fetch connection...\n")

    # Step 1: Collect Reels
    print("[1/5] Collecting Instagram Trending Reels...")
    try:
        reels = client.fetch_trending_reels()
    except PaymentRequiredError as e:
        print(f"\n[HTTP 402 PAYMENT REQUIRED] {e}")
        print("-> The Social Fetch account requires active subscription/credits.")
        print("-> Live collection halted. Switching to mock mode is recommended (--mock).")
        return 2
    except AuthenticationError as e:
        print(f"\n[HTTP 401 AUTHENTICATION ERROR] {e}")
        return 1
    except ForbiddenError as e:
        print(f"\n[HTTP 403 FORBIDDEN] {e}")
        return 1
    except RateLimitError as e:
        print(f"\n[HTTP 429 RATE LIMIT EXCEEDED] Retry-After: {e.retry_after}s")
        return 1
    except ProviderServerError as e:
        print(f"\n[HTTP 5xx SERVER ERROR] {e}")
        return 1
    except TrendProviderError as e:
        print(f"\n[PROVIDER ERROR] {e}")
        return 1

    print(f"      -> Retrieved {len(reels)} reels.")

    # Step 2: Store in SQLite
    print("[2/5] Persisting reels in SQLite database...")
    saved_count = db.save_reels(reels)
    print(f"      -> Successfully saved/updated {saved_count} records in {db.db_path.name}")

    # Step 3: Analyze Content, Categories & Hooks
    print("[3/5] Performing marketing trend & hook analysis...")
    analyses = [analyze_reel(r) for r in reels]
    db.save_analyses(analyses)
    print(f"      -> Analyzed {len(analyses)} reels across target marketing niches.")

    # Step 4: Generate AdSync Video Concepts
    print("[4/5] Generating original AdSync Reel concepts...")
    ideas = generate_batch_ideas(reels, analyses)
    db.save_ideas(ideas)
    print(f"      -> Generated {len(ideas)} original AdSync video concepts.")

    # Step 5: Generate Daily Intelligence Report
    print("[5/5] Compiling Daily Trend Intelligence Report...")
    reporter = DailyReportGenerator(db)
    report_md = reporter.generate(is_mock=use_mock)
    report_file = reporter.output_dir / f"daily_report_{Path(config.db_path).stem}.md"
    print(f"      -> Daily report generated at: {reporter.output_dir}")

    print("\n" + "=" * 75)
    print(" Pipeline Execution Complete!")
    print("=" * 75)

    # Preview Top 3 ideas in console
    print("\n--- TOP ADSYNC REEL CONCEPTS (PREVIEW) ---")
    for i, idea in enumerate(ideas[:3], 1):
        print(f"\n#{i}. [{idea.target_category}] {idea.topic} (Score: {idea.opportunity_score})")
        print(f"   Visual Style: {idea.faceless_short_style}")
        print(f"   Lead Hook:    \"{idea.hooks[0]}\"")
        print(f"   CTA:          {idea.call_to_action}")

    return 0


def probe_connection():
    """Performs a safe configuration and credential check."""
    config = get_config()
    client = SocialFetchClient(config, use_mock=config.force_mock_mode)
    diag = client.validate_connection()

    print("=" * 65)
    print(" Social Fetch API Connection Diagnostics")
    print("=" * 65)
    print(f" Provider:              {diag['provider']}")
    print(f" Target Endpoint:       {diag['endpoint']}")
    print(f" Execution Mode:        {diag['mode']}")
    print(f" Configured API Key:    {diag['masked_key']}")
    print(f" Has Real Key:          {diag['api_key_configured']}")
    print(f" Mock Fixtures Found:   {diag['fixture_available']}")
    print(f" Readiness Status:      {diag['status']}")
    print("=" * 65)

    if not config.is_configured:
        print("\n[NOTE] API key is currently set to placeholder in .env.")
        print("To configure real credentials, add your key to trend_engine/.env:")
        print("  SOCIAL_FETCH_API_KEY=your_actual_key_here")


def show_stats():
    """Prints SQLite storage metrics."""
    config = get_config()
    db = DatabaseRepository(config.db_path)
    stats = db.get_summary_stats()

    print("=" * 65)
    print(" AdSync Trend Database Statistics")
    print("=" * 65)
    print(f" Total Ingested Reels:   {stats.get('total_reels', 0)}")
    print(f"   - Mock Test Reels:    {stats.get('mock_reels', 0)}")
    print(f"   - Live Reels:         {stats.get('live_reels', 0)}")
    print(f" Generated AdSync Ideas: {stats.get('total_ideas', 0)}")
    print("\n Category Breakdown:")
    for cat, cnt in stats.get("categories", {}).items():
        print(f"   • {cat:<24} {cnt} reels")
    print("\n Top Content Formats:")
    for fmt, cnt in stats.get("formats", {}).items():
        print(f"   • {fmt:<35} {cnt}")
    print("=" * 65)


def test_live_single_reel() -> int:
    """Performs a safe, single-request live probe against Social Fetch."""
    config = get_config()
    print("=" * 65)
    print(" Social Fetch Live Single-Request Probe")
    print("=" * 65)

    if config.force_mock_mode:
        print("[SAFETY LOCK ACTIVE] FORCE_MOCK_MODE=1 is set in .env.")
        print("Live requests are blocked. To perform this probe, temporarily set:")
        print("  FORCE_MOCK_MODE=0")
        print("in trend_engine/.env and ensure SOCIAL_FETCH_API_KEY has active credits.")
        return 1

    if not config.is_configured:
        print("[ERROR] No real API key configured. Update SOCIAL_FETCH_API_KEY in .env.")
        return 1

    client = SocialFetchClient(config, use_mock=False)
    print(f"Target Endpoint: {config.base_url}/v2/instagram/reels/trending")
    print(f"Configured Key:  {config.masked_api_key}")
    print("Sending single probe request (timeout 20s)...")

    try:
        res = client.probe_single_live_reel()
        if res.get("status") == "EMPTY_OR_UNEXPECTED_PAYLOAD":
            print(f"\n[RESPONSE NOTICE - HTTP {res.get('status_code')}]")
            print(f"Message: {res.get('message')}")
            print(f"Detected Keys/Type in Payload: {res.get('payload_keys')}")
            print("Provider Headers:", res.get("headers"))
            return 0

        print("\n[PROBE SUCCESS - HTTP 200 OK]")
        print(f"Endpoint: {res.get('endpoint')}")
        print("Provider Headers:", res.get("headers"))
        if "reel_sample" in res:
            sample = res["reel_sample"]
            plays = sample.get("plays")
            likes = sample.get("likes")
            shares = sample.get("shares")
            plays_str = f"{plays:,}" if plays is not None else "NULL (unrecorded/hidden)"
            likes_str = f"{likes:,}" if likes is not None else "NULL (unrecorded/hidden)"
            shares_str = f"{shares:,}" if shares is not None else "NULL (unrecorded/hidden)"

            print("\nExtracted Live Reel Sample:")
            print(f"  • Shortcode:   {sample.get('shortcode')}")
            print(f"  • URL:         {sample.get('url')}")
            print(f"  • Author:      @{sample.get('author') or sample.get('author_username')}")
            print(f"  • Plays/Views: {plays_str}")
            print(f"  • Likes:       {likes_str}")
            print(f"  • Shares:      {shares_str}")
            print(f"  • Audio:       {sample.get('audio')}")
            print(f"  • Caption:     {sample.get('caption_preview')}")
        print("\n[VERIFIED] Field mapping & schema parsing validated successfully on live payload.")
        return 0
    except PaymentRequiredError as e:
        print(f"\n[HTTP 402 PAYMENT REQUIRED] {e}")
        print("-> Diagnostic: The Social Fetch account requires active credits/subscription.")
        print("-> No further requests were made. Zero additional credits consumed.")
        return 2
    except AuthenticationError as e:
        print(f"\n[HTTP 401 AUTHENTICATION FAILED] {e}")
        return 1
    except ForbiddenError as e:
        print(f"\n[HTTP 403 FORBIDDEN] {e}")
        return 1
    except RateLimitError as e:
        print(f"\n[HTTP 429 RATE LIMIT EXCEEDED] Retry-After: {e.retry_after}s")
        return 1
    except ProviderServerError as e:
        print(f"\n[HTTP 5xx SERVER ERROR] {e}")
        return 1
    except TrendProviderError as e:
        print(f"\n[PROVIDER ERROR] {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="AdSync Trend Engine CLI Controller")
    parser.add_argument("--mock", action="store_true", default=True, help="Run in mock mode using test fixtures (default)")
    parser.add_argument("--live", action="store_true", help="Attempt live API retrieval (requires valid credits)")
    parser.add_argument("--probe", action="store_true", help="Check API configuration and readiness safely")
    parser.add_argument("--test-live-single", action="store_true", help="Perform a safe, single-request live probe")
    parser.add_argument("--stats", action="store_true", help="Display stored database statistics")
    parser.add_argument("--report", action="store_true", help="Recompile daily report from existing database")

    args = parser.parse_args()

    if args.test_live_single:
        sys.exit(test_live_single_reel())

    if args.probe:
        probe_connection()
        return

    if args.stats:
        show_stats()
        return

    if args.report:
        config = get_config()
        db = DatabaseRepository(config.db_path)
        reporter = DailyReportGenerator(db)
        md = reporter.generate(is_mock=True)
        print(md[:1500] + "\n\n... [Report continues in reports/ directory] ...")
        return

    use_mock = not args.live
    sys.exit(run_pipeline(use_mock=use_mock))


if __name__ == "__main__":
    main()

