"""Instagram Competitor Intelligence Engine for AdSync Marketing.

Provides comprehensive competitor benchmarking, profile synchronization,
and content pattern analysis across AdSync's 6 target competitor verticals:
1. Digital Marketing Agencies
2. Meta Ads Specialists
3. Lead Generation Experts
4. Marketing Automation
5. Branding Agencies
6. Real Estate Marketing

Key Capabilities:
- Competitor management: add, edit, list, and delete competitor accounts.
- Profile and Reel tracking: leverages SocialFetchClient to sync profile data and recent reels.
- Time-series snapshots: logs view, like, comment, and share metrics across sync runs.
- Best-performing reels detection: ranks competitor output using EngagementScoringEngine.
- Cross-competitor comparison: benchmarks creators by average views, engagement rates, and scores.
- Content pattern recognition: detects recurring hook patterns, formats, and top keywords.
- Safety & integrity: supports missing/private profiles safely, deduplicates records, and enforces mock mode.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid
import re
from typing import List, Optional, Dict, Any, Tuple, Set
from pathlib import Path

from ..storage.models import ReelItem, CompetitorProfile, ReelSnapshot
from ..storage.database import DatabaseRepository
from ..providers.social_fetch import SocialFetchClient
from .scoring import EngagementScoringEngine, ReelScoreBreakdown, ScoringWeights
from .hook_extractor import extract_hook_sentence, classify_hook_pattern, identify_content_format


COMPETITOR_CATEGORIES = [
    "Digital Marketing Agencies",
    "Meta Ads Specialists",
    "Lead Generation Experts",
    "Marketing Automation",
    "Branding Agencies",
    "Real Estate Marketing",
]


@dataclass
class CompetitorPerformanceSummary:
    """Consolidated performance profile and content insights for a single competitor."""
    handle: str
    category: str
    display_name: Optional[str]
    bio: Optional[str]
    follower_count: Optional[int]
    is_private: bool
    verified: bool
    reels_tracked: int
    total_views: Optional[int]
    avg_views_per_reel: Optional[float]
    avg_like_rate: Optional[float]
    avg_comment_rate: Optional[float]
    avg_share_rate: Optional[float]
    avg_overall_engagement_rate: Optional[float]
    avg_popularity_score: Optional[float]
    avg_engagement_score: Optional[float]
    top_reels: List[Dict[str, Any]]
    recurring_topics: List[Dict[str, Any]]
    dominant_hook_types: List[Dict[str, Any]]
    dominant_formats: List[Dict[str, Any]]
    last_synced_at: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompetitorComparisonReport:
    """Cross-competitor competitive benchmark across a category or overall."""
    category: Optional[str]
    generated_at: str
    total_competitors: int
    competitors: List[CompetitorPerformanceSummary]
    rankings_by_popularity: List[str]     # handles sorted by avg_popularity_score DESC
    rankings_by_engagement: List[str]     # handles sorted by avg_engagement_score DESC
    rankings_by_reach: List[str]          # handles sorted by avg_views_per_reel DESC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "generated_at": self.generated_at,
            "total_competitors": self.total_competitors,
            "competitors": [c.to_dict() for c in self.competitors],
            "rankings_by_popularity": self.rankings_by_popularity,
            "rankings_by_engagement": self.rankings_by_engagement,
            "rankings_by_reach": self.rankings_by_reach,
        }


class CompetitorIntelligenceEngine:
    """Manages competitor profiles, synchronizes snapshots, and computes competitive analytics."""

    def __init__(
        self,
        db_repo: DatabaseRepository,
        client: Optional[SocialFetchClient] = None,
        scoring_weights: Optional[ScoringWeights] = None
    ):
        self.db = db_repo
        self.client = client
        self.scoring_engine = EngagementScoringEngine(weights=scoring_weights)

    def validate_category(self, category: str) -> str:
        """Validates that a category matches AdSync's 6 core competitor categories."""
        clean = category.strip()
        matched = next((c for c in COMPETITOR_CATEGORIES if c.lower() == clean.lower()), None)
        if not matched:
            raise ValueError(
                f"Invalid competitor category: '{category}'. Allowed categories: {COMPETITOR_CATEGORIES}"
            )
        return matched

    # =========================================================================
    # 1. Competitor Management (CRUD)
    # =========================================================================

    def add_competitor(
        self,
        handle: str,
        category: str,
        notes: Optional[str] = None
    ) -> CompetitorProfile:
        """Adds a competitor profile to the tracking registry."""
        if not handle or not handle.strip():
            raise ValueError("Competitor handle cannot be empty.")

        clean_handle = handle.strip().lstrip("@").lower()
        valid_cat = self.validate_category(category)

        # Check existing
        existing = self.db.get_competitor(clean_handle)
        if existing:
            # Update category and notes if needed
            existing.category = valid_cat
            if notes is not None:
                existing.notes = notes
            self.db.save_competitor(existing)
            return existing

        profile = CompetitorProfile(
            handle=clean_handle,
            category=valid_cat,
            notes=notes
        )
        self.db.save_competitor(profile)
        return profile

    def update_competitor(
        self,
        handle: str,
        category: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[CompetitorProfile]:
        """Updates category or notes for an existing competitor."""
        profile = self.db.get_competitor(handle)
        if not profile:
            return None

        if category is not None:
            profile.category = self.validate_category(category)
        if notes is not None:
            profile.notes = notes

        self.db.save_competitor(profile)
        return profile

    def remove_competitor(self, handle: str) -> bool:
        """Removes a competitor from the tracking registry."""
        return self.db.delete_competitor(handle)

    def list_competitors(self, category: Optional[str] = None) -> List[CompetitorProfile]:
        """Lists competitors, optionally filtered by category."""
        return self.db.get_competitors(category=category)

    def get_competitor(self, handle: str) -> Optional[CompetitorProfile]:
        """Retrieves a single competitor by handle."""
        return self.db.get_competitor(handle)

    # =========================================================================
    # 2. Ingestion & Snapshot Synchronization
    # =========================================================================

    def sync_competitor_profile(
        self,
        handle: str,
        limit: int = 15
    ) -> Tuple[Optional[CompetitorProfile], List[ReelItem]]:
        """Synchronizes competitor profile info and recent reels from SocialFetchClient.
        
        Stores:
        - CompetitorProfile updates in `competitors` table.
        - ReelItem records in `reels` table (deduplicated).
        - Historical snapshot metrics in `competitor_reel_snapshots` table.
        """
        clean_handle = handle.strip().lstrip("@").lower()
        competitor = self.db.get_competitor(clean_handle)
        if not competitor:
            raise ValueError(f"Competitor '{clean_handle}' is not registered. Add competitor first.")

        if not self.client:
            raise RuntimeError("SocialFetchClient is not configured on CompetitorIntelligenceEngine.")

        # Fetch profile and media using existing client method
        reels, profile_dict, _ = self.client.fetch_reels_by_creator(clean_handle, limit=limit)

        now_str = datetime.now(timezone.utc).isoformat()

        # Update CompetitorProfile if profile metadata is provided
        if profile_dict:
            competitor.display_name = profile_dict.get("displayName") or competitor.display_name
            competitor.bio = profile_dict.get("bio") or competitor.bio
            competitor.avatar_url = profile_dict.get("avatarUrl") or competitor.avatar_url
            competitor.verified = bool(profile_dict.get("verified", False))
            competitor.is_private = bool(profile_dict.get("privateAccount", False))
            counts = profile_dict.get("counts") or {}
            competitor.follower_count = counts.get("followers") or competitor.follower_count
            competitor.following_count = counts.get("following") or competitor.following_count
            competitor.posts_count = counts.get("posts") or competitor.posts_count

        competitor.last_fetched_at = now_str
        self.db.save_competitor(competitor)

        # Handle private profiles or empty media grids safely
        if not reels:
            return competitor, []

        # Save reels (deduplicated via SQLite primary key upsert)
        self.db.save_reels(reels)

        # Record snapshots for time-series tracking
        for r in reels:
            snapshot_id = f"snap_{r.reel_id}_{uuid.uuid4().hex[:8]}"
            snap = ReelSnapshot(
                snapshot_id=snapshot_id,
                reel_id=r.reel_id,
                handle=clean_handle,
                captured_at=now_str,
                play_count=r.play_count,
                like_count=r.like_count,
                comment_count=r.comment_count,
                share_count=r.share_count,
            )
            self.db.save_reel_snapshot(snap)

        return competitor, reels

    # =========================================================================
    # 3. Analytics & Performance Summaries
    # =========================================================================

    def summarize_competitor(self, handle: str) -> Optional[CompetitorPerformanceSummary]:
        """Calculates deep analytics, top reels, and content patterns for a competitor."""
        clean_handle = handle.strip().lstrip("@").lower()
        profile = self.db.get_competitor(clean_handle)
        if not profile:
            return None

        # Fetch all reels authored by this competitor from SQLite
        all_reels = self.db.get_reels(limit=250)
        competitor_reels = [
            r for r in all_reels
            if r.author_username and r.author_username.strip().lstrip("@").lower() == clean_handle
        ]

        if not competitor_reels:
            return CompetitorPerformanceSummary(
                handle=clean_handle,
                category=profile.category,
                display_name=profile.display_name,
                bio=profile.bio,
                follower_count=profile.follower_count,
                is_private=profile.is_private,
                verified=profile.verified,
                reels_tracked=0,
                total_views=None,
                avg_views_per_reel=None,
                avg_like_rate=None,
                avg_comment_rate=None,
                avg_share_rate=None,
                avg_overall_engagement_rate=None,
                avg_popularity_score=None,
                avg_engagement_score=None,
                top_reels=[],
                recurring_topics=[],
                dominant_hook_types=[],
                dominant_formats=[],
                last_synced_at=profile.last_fetched_at,
            )

        # Score and analyze each reel
        scored_reels: List[Tuple[ReelItem, ReelScoreBreakdown]] = []
        view_counts: List[int] = []
        like_rates: List[float] = []
        comment_rates: List[float] = []
        share_rates: List[float] = []
        overall_rates: List[float] = []
        pop_scores: List[float] = []
        eng_scores: List[float] = []

        hook_type_counts: Dict[str, int] = {}
        format_counts: Dict[str, int] = {}
        keyword_counts: Dict[str, int] = {}

        for r in competitor_reels:
            score_bd = self.scoring_engine.score_reel(r, all_reels=competitor_reels)
            scored_reels.append((r, score_bd))

            if r.play_count is not None and r.play_count > 0:
                view_counts.append(r.play_count)

            rates = score_bd.rates
            if rates.like_rate is not None:
                like_rates.append(rates.like_rate)
            if rates.comment_rate is not None:
                comment_rates.append(rates.comment_rate)
            if rates.share_rate is not None:
                share_rates.append(rates.share_rate)
            if rates.overall_rate is not None:
                overall_rates.append(rates.overall_rate)

            if score_bd.popularity_score is not None:
                pop_scores.append(score_bd.popularity_score)
            if score_bd.engagement_score is not None:
                eng_scores.append(score_bd.engagement_score)

            # Content patterns
            hook_text = extract_hook_sentence(r.caption)
            hook_type, _ = classify_hook_pattern(hook_text)
            hook_type_counts[hook_type] = hook_type_counts.get(hook_type, 0) + 1

            fmt = identify_content_format(r)
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

            # Keyword patterns
            tokens = re.findall(r"[a-z0-9\+\_]{4,}", f"{r.caption.lower()} {' '.join(r.hashtags).lower()}")
            for t in tokens:
                if t not in {"reels", "video", "instagram", "post", "watch", "link", "save"}:
                    keyword_counts[t] = keyword_counts.get(t, 0) + 1

        # Averages
        total_views = sum(view_counts) if view_counts else None
        avg_views = round(sum(view_counts) / len(view_counts), 1) if view_counts else None
        avg_like = round(sum(like_rates) / len(like_rates), 3) if like_rates else None
        avg_comm = round(sum(comment_rates) / len(comment_rates), 3) if comment_rates else None
        avg_share = round(sum(share_rates) / len(share_rates), 3) if share_rates else None
        avg_overall = round(sum(overall_rates) / len(overall_rates), 3) if overall_rates else None
        avg_pop = round(sum(pop_scores) / len(pop_scores), 2) if pop_scores else None
        avg_eng = round(sum(eng_scores) / len(eng_scores), 2) if eng_scores else None

        # Sort top reels by composite engagement/popularity
        scored_reels.sort(
            key=lambda x: (x[1].composite_engagement_score, x[0].play_count or 0),
            reverse=True
        )

        top_reels_summary = [
            {
                "reel_id": r.reel_id,
                "shortcode": r.shortcode,
                "url": r.url,
                "caption": r.caption[:120] + "..." if len(r.caption) > 120 else r.caption,
                "views": r.play_count,
                "likes": r.like_count,
                "comments": r.comment_count,
                "shares": r.share_count,
                "overall_engagement_rate": bd.rates.overall_rate,
                "popularity_score": bd.popularity_score,
                "engagement_score": bd.engagement_score,
                "published_at": r.published_at,
            }
            for r, bd in scored_reels[:5]
        ]

        # Recurring topics
        recurring_topics = [
            {"keyword": kw, "frequency": count}
            for kw, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        ]

        dominant_hooks = [
            {"hook_type": ht, "count": count, "percentage": round((count / len(competitor_reels)) * 100, 1)}
            for ht, count in sorted(hook_type_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        dominant_fmts = [
            {"format": fmt, "count": count, "percentage": round((count / len(competitor_reels)) * 100, 1)}
            for fmt, count in sorted(format_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return CompetitorPerformanceSummary(
            handle=clean_handle,
            category=profile.category,
            display_name=profile.display_name,
            bio=profile.bio,
            follower_count=profile.follower_count,
            is_private=profile.is_private,
            verified=profile.verified,
            reels_tracked=len(competitor_reels),
            total_views=total_views,
            avg_views_per_reel=avg_views,
            avg_like_rate=avg_like,
            avg_comment_rate=avg_comm,
            avg_share_rate=avg_share,
            avg_overall_engagement_rate=avg_overall,
            avg_popularity_score=avg_pop,
            avg_engagement_score=avg_eng,
            top_reels=top_reels_summary,
            recurring_topics=recurring_topics,
            dominant_hook_types=dominant_hooks,
            dominant_formats=dominant_fmts,
            last_synced_at=profile.last_fetched_at,
        )

    # =========================================================================
    # 4. Cross-Competitor Comparison Report
    # =========================================================================

    def compare_competitors(self, category: Optional[str] = None) -> CompetitorComparisonReport:
        """Generates a competitive benchmark comparing competitors across category or portfolio."""
        competitors = self.db.get_competitors(category=category)
        summaries: List[CompetitorPerformanceSummary] = []

        for c in competitors:
            s = self.summarize_competitor(c.handle)
            if s:
                summaries.append(s)

        # Leaderboard rankings
        rank_pop = sorted(
            [s for s in summaries if s.avg_popularity_score is not None],
            key=lambda x: x.avg_popularity_score or 0.0,
            reverse=True
        )
        rank_eng = sorted(
            [s for s in summaries if s.avg_engagement_score is not None],
            key=lambda x: x.avg_engagement_score or 0.0,
            reverse=True
        )
        rank_reach = sorted(
            [s for s in summaries if s.avg_views_per_reel is not None],
            key=lambda x: x.avg_views_per_reel or 0.0,
            reverse=True
        )

        return CompetitorComparisonReport(
            category=category,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_competitors=len(summaries),
            competitors=summaries,
            rankings_by_popularity=[s.handle for s in rank_pop],
            rankings_by_engagement=[s.handle for s in rank_eng],
            rankings_by_reach=[s.handle for s in rank_reach],
        )
