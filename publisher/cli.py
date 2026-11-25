"""Command Line Interface for the Instagram Reels Publisher."""
import argparse
import sys
import json
from pathlib import Path
from publisher.config import PublisherConfig
from publisher.manager import ReelPublishManager


def main():
    parser = argparse.ArgumentParser(description="AdSync Instagram Reels Publisher CLI")
    parser.add_argument("--video", required=True, help="Path to rendered MP4 video file")
    parser.add_argument("--caption", required=True, help="Caption copy for the Reel")
    parser.add_argument("--hashtags", nargs="*", default=[], help="List of hashtags (space-separated)")
    parser.add_argument("--video-url", default=None, help="Public HTTPS URL for video hosting")
    parser.add_argument("--schedule", type=int, default=None, help="Scheduled publish timestamp (Unix epoch)")
    parser.add_argument("--live", action="store_true", help="Publish directly via Graph API (requires credentials)")
    parser.add_argument("--list", action="store_true", help="List recent publication logs")

    args = parser.parse_args()

    config = PublisherConfig.from_env()
    # If not explicitly --live, force dry run
    dry_run = not args.live

    manager = ReelPublishManager(config)

    print("=" * 65)
    print(" AdSync Instagram Reels Publisher (Phase 4A)")
    print("=" * 65)
    print(f"Mode: {'LIVE PRODUCTION' if not dry_run else 'DRY RUN / SIMULATION'}")
    print(f"Video Path: {args.video}")
    print(f"Hashtags:   {args.hashtags}")
    if args.schedule:
        print(f"Scheduled Time: {args.schedule}")
    print("-" * 65)

    res = manager.publish_reel(
        video_path=args.video,
        caption_text=args.caption,
        hashtags=args.hashtags,
        video_url=args.video_url,
        scheduled_time=args.schedule,
        dry_run=dry_run
    )

    print(f"Publication ID: {res.publication_id}")
    print(f"Status:         {res.status}")
    if res.post_id:
        print(f"Post ID:        {res.post_id}")
    if res.permalink:
        print(f"Permalink:      {res.permalink}")
    if res.error_message:
        print(f"Error:          {res.error_message}")
    print("=" * 65)

    if res.status in ("PUBLISHED", "DRY_RUN", "SCHEDULED"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

