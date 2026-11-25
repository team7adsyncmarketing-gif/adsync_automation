"""Instagram Reel Engagement & Popularity Scoring Engine for AdSync Marketing.

Provides principled, mathematically sound scoring models across:
1. Popularity Score:
   - Evaluates reach volume (views, likes, comments, shares) with log-scale normalization.
2. Engagement Score:
   - Evaluates interaction depth: like rate, comment rate, share rate, and overall engagement.
   - Missing metrics remain unknown (None), not treated as zero.
3. Recency Score:
   - Exponential time-decay scoring giving preference to recent content without discarding older hits.
4. Niche Relevance Score:
   - Evaluates alignment with AdSync's 8 core marketing verticals.
5. Creator Performance:
   - Benchmark comparison against the creator's other known reels when sufficient history exists (>= 3 reels).
   - Never fabricates creator benchmarks when insufficient data is available.

Generates three separate rankings:
- Most Popular
- Best Engagement
- Rising Content
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math
from typing import List, Optional, Dict, Any, Tuple
from ..storage.models import ReelItem
from .categorization import classify_reel_category, CATEGORY_TAXONOMY


@dataclass
class ScoringWeights:
    """Configurable weights for scoring components and composite rankings."""
    # Popularity interaction weights
    pop_view_weight: float = 0.40
    pop_like_weight: float = 0.25
    pop_comment_weight: float = 0.20
    pop_share_weight: float = 0.15

    # Engagement interaction weights (when computing overall engagement rate)
    eng_like_weight: float = 1.0
    eng_comment_weight: float = 2.5
    eng_share_weight: float = 4.0

    # Composite Ranking: Most Popular
    rank_popular_pop_weight: float = 0.70
    rank_popular_eng_weight: float = 0.20
    rank_popular_niche_weight: float = 0.10

    # Composite Ranking: Best Engagement
    rank_eng_eng_weight: float = 0.70
    rank_eng_pop_weight: float = 0.15
    rank_eng_niche_weight: float = 0.15

    # Composite Ranking: Rising Content
    rank_rising_recency_weight: float = 0.45
    rank_rising_eng_weight: float = 0.30
    rank_rising_pop_weight: float = 0.15
    rank_rising_niche_weight: float = 0.10

    # Recency half-life in days (time after which recency score drops by 50%)
    recency_half_life_days: float = 7.0

    # Minimum creator reel history needed to compute historical creator benchmarks
    min_creator_history_count: int = 3


@dataclass
class EngagementRates:
    """Interaction rates per 100 views (percentages).
    Missing metrics remain None rather than 0.0 to prevent false assumptions.
    """
    like_rate: Optional[float] = None       # likes / views * 100
    comment_rate: Optional[float] = None    # comments / views * 100
    share_rate: Optional[float] = None      # shares / views * 100
    overall_rate: Optional[float] = None    # weighted interactions / views * 100

    def to_dict(self) -> Dict[str, Optional[float]]:
        return asdict(self)


@dataclass
class CreatorBenchmark:
    """Historical comparison against the creator's other reels."""
    has_sufficient_data: bool = False
    creator_reel_count: int = 0
    creator_avg_views: Optional[float] = None
    creator_avg_overall_rate: Optional[float] = None
    views_multiplier: Optional[float] = None  # this_reel.views / creator_avg_views
    rate_multiplier: Optional[float] = None   # this_reel.overall_rate / creator_avg_rate
    performance_score: Optional[float] = None  # Normalized 0-100 score relative to creator baseline

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReelScoreBreakdown:
    """Detailed scoring breakdown and raw metrics for a single Reel."""
    reel_id: str
    shortcode: str
    author_username: str
    category: str
    
    # Raw metrics preserved alongside calculations
    raw_views: Optional[int]
    raw_likes: Optional[int]
    raw_comments: Optional[int]
    raw_shares: Optional[int]
    published_at: Optional[str]
    age_in_days: Optional[float]

    # Individual Dimension Scores (Normalized 0.0 - 100.0)
    popularity_score: Optional[float]
    engagement_score: Optional[float]
    recency_score: Optional[float]
    niche_relevance_score: float

    # Detailed calculated rates
    rates: EngagementRates
    creator_benchmark: CreatorBenchmark

    # Composite Ranking Scores (0.0 - 100.0)
    composite_popular_score: float
    composite_engagement_score: float
    composite_rising_score: float

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rates"] = self.rates.to_dict()
        d["creator_benchmark"] = self.creator_benchmark.to_dict()
        return d


class EngagementScoringEngine:
    """Orchestrates multi-dimensional scoring and ranking for Instagram Reels."""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()

    def parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Safely parses ISO timestamp into a timezone-aware UTC datetime."""
        if not date_str or not isinstance(date_str, str):
            return None
        clean_str = date_str.strip()
        if not clean_str:
            return None
        
        # Try standard ISO formats
        try:
            # Handle trailing Z
            if clean_str.endswith("Z"):
                clean_str = clean_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def calculate_rates(self, reel: ReelItem) -> EngagementRates:
        """Calculates like rate, comment rate, share rate, and overall rate.
        If play_count is missing or <= 0, rates cannot be calculated and return None.
        If an individual interaction count is missing/None, that rate returns None.
        """
        views = reel.play_count
        if views is None or views <= 0:
            return EngagementRates()

        like_rate = round((reel.like_count / views) * 100.0, 3) if reel.like_count is not None else None
        comment_rate = round((reel.comment_count / views) * 100.0, 3) if reel.comment_count is not None else None
        share_rate = round((reel.share_count / views) * 100.0, 3) if reel.share_count is not None else None

        # Overall engagement rate: sum of available weighted interactions / views * 100
        # If no interaction metrics are available, overall_rate is None
        weighted_sum = 0.0
        available_count = 0

        if reel.like_count is not None:
            weighted_sum += reel.like_count * self.weights.eng_like_weight
            available_count += 1
        if reel.comment_count is not None:
            weighted_sum += reel.comment_count * self.weights.eng_comment_weight
            available_count += 1
        if reel.share_count is not None:
            weighted_sum += reel.share_count * self.weights.eng_share_weight
            available_count += 1

        if available_count == 0:
            overall_rate = None
        else:
            overall_rate = round((weighted_sum / views) * 100.0, 3)

        return EngagementRates(
            like_rate=like_rate,
            comment_rate=comment_rate,
            share_rate=share_rate,
            overall_rate=overall_rate,
        )

    def calculate_popularity_score(self, reel: ReelItem) -> Optional[float]:
        """Calculates Popularity Score (0.0 to 100.0) based on log-scale reach.
        
        Uses logarithmic scaling: log10(1 + count) / log10(1 + target_scale) * 100.
        Targets:
          - Views: 1,000,000 -> 100 pts (weight 0.40)
          - Likes: 50,000    -> 100 pts (weight 0.25)
          - Comments: 2,500  -> 100 pts (weight 0.20)
          - Shares: 10,000   -> 100 pts (weight 0.15)
        
        If all volume metrics are None, returns None (missing metrics).
        Available metrics are weighted proportionally to their configured weights.
        """
        metrics = [
            (reel.play_count, 1_000_000, self.weights.pop_view_weight),
            (reel.like_count, 50_000, self.weights.pop_like_weight),
            (reel.comment_count, 2_500, self.weights.pop_comment_weight),
            (reel.share_count, 10_000, self.weights.pop_share_weight),
        ]

        active_weighted_scores = 0.0
        active_weights = 0.0

        for val, target, weight in metrics:
            if val is not None:
                # Logarithmic scale for viral reach
                log_val = math.log10(1.0 + max(0, val))
                log_target = math.log10(1.0 + target)
                metric_score = min(100.0, (log_val / log_target) * 100.0)
                active_weighted_scores += metric_score * weight
                active_weights += weight

        if active_weights == 0.0:
            return None

        # Re-normalize across available metrics
        score = active_weighted_scores / active_weights
        return round(min(100.0, max(0.0, score)), 2)

    def calculate_engagement_score(self, rates: EngagementRates) -> Optional[float]:
        """Calculates Engagement Score (0.0 to 100.0).
        
        Evaluates interaction quality per view:
        - Like rate benchmark: 5.0% -> 60 pts
        - Comment rate benchmark: 0.5% -> 80 pts
        - Share rate benchmark: 1.5% -> 90 pts
        - Overall weighted rate benchmark: 10.0% -> 100 pts
        
        Returns None if rates could not be calculated (e.g. play_count is None or 0).
        """
        if rates.overall_rate is None:
            return None

        # S-curve / piecewise linear normalization around benchmark rates
        # 10% weighted engagement rate = 80 points; 20%+ = 100 points
        rate = rates.overall_rate
        if rate <= 0:
            score = 0.0
        else:
            # log-based rate curve: rate of 1.0% -> ~25 pts; 5.0% -> ~55 pts; 10.0% -> ~75 pts; 20.0% -> ~95 pts
            score = min(100.0, math.sqrt(rate / 20.0) * 100.0)

        # Bonus for high comment/share ratio if available
        bonus = 0.0
        if rates.share_rate is not None and rates.like_rate is not None and rates.like_rate > 0:
            share_to_like = rates.share_rate / rates.like_rate
            if share_to_like > 0.2:  # High virality indicator
                bonus += min(10.0, share_to_like * 10.0)

        final_score = min(100.0, max(0.0, score + bonus))
        return round(final_score, 2)

    def calculate_recency_score(
        self,
        published_at_str: Optional[str],
        reference_time: Optional[datetime] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculates Recency Score (0.0 to 100.0) using exponential half-life decay.
        
        Formula: score = 100 * (0.5 ** (age_in_days / half_life_days))
        A half-life of 7 days means:
          - 0 days old -> 100.0
          - 7 days old -> 50.0
          - 14 days old -> 25.0
          - 28 days old -> 6.25
        
        Returns (recency_score, age_in_days).
        If published_at is missing or invalid, returns (None, None).
        """
        dt = self.parse_datetime(published_at_str)
        if dt is None:
            return None, None

        ref = reference_time or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        age_seconds = (ref - dt).total_seconds()
        # Handle future dates safely by clamping age to 0
        age_in_days = max(0.0, age_seconds / 86400.0)

        half_life = max(0.1, self.weights.recency_half_life_days)
        score = 100.0 * (0.5 ** (age_in_days / half_life))
        return round(score, 2), round(age_in_days, 2)

    def calculate_niche_relevance_score(self, reel: ReelItem) -> Tuple[str, float]:
        """Calculates Niche Relevance Score (0.0 to 100.0) based on AdSync's 8 categories.
        Reuses existing classify_reel_category and normalizes confidence to 0-100 scale.
        """
        category, confidence = classify_reel_category(reel)
        if category == "Other / Irrelevant":
            score = 15.0  # minimal baseline
        else:
            # confidence is 0.40 to 0.98 -> map to 40.0 - 98.0
            score = round(confidence * 100.0, 2)

        return category, score

    def calculate_creator_benchmark(
        self,
        reel: ReelItem,
        creator_reels: List[ReelItem],
        this_rates: EngagementRates
    ) -> CreatorBenchmark:
        """Compares this Reel against the creator's other reels when sufficient data exists.
        
        Requires at least `min_creator_history_count` (default 3) distinct reels
        from this creator in the historical dataset.
        If fewer than 3 reels exist, returns `has_sufficient_data=False` with None values.
        """
        if not reel.author_username:
            return CreatorBenchmark(has_sufficient_data=False)

        # Filter other reels by this author (excluding current reel)
        author = reel.author_username.lower().strip()
        peer_reels = [
            r for r in creator_reels
            if r.author_username and r.author_username.lower().strip() == author
            and r.reel_id != reel.reel_id
        ]

        total_creator_reels = len(peer_reels) + 1
        if total_creator_reels < self.weights.min_creator_history_count:
            return CreatorBenchmark(
                has_sufficient_data=False,
                creator_reel_count=total_creator_reels,
            )

        # Calculate creator baseline averages across all creator reels
        all_reels_for_author = peer_reels + [reel]
        view_samples = [r.play_count for r in all_reels_for_author if r.play_count is not None and r.play_count > 0]
        avg_views = (sum(view_samples) / len(view_samples)) if view_samples else None

        # Engagement rate samples
        rate_samples = []
        for r in all_reels_for_author:
            rates = self.calculate_rates(r)
            if rates.overall_rate is not None:
                rate_samples.append(rates.overall_rate)
        avg_rate = (sum(rate_samples) / len(rate_samples)) if rate_samples else None

        # Multipliers
        views_mult = (reel.play_count / avg_views) if (reel.play_count and avg_views and avg_views > 0) else None
        rate_mult = (this_rates.overall_rate / avg_rate) if (this_rates.overall_rate and avg_rate and avg_rate > 0) else None

        # Performance score (50.0 is exact average; 100.0 is 2.5x+ average)
        if rate_mult is not None:
            perf_score = min(100.0, max(0.0, round(50.0 * rate_mult, 2)))
        elif views_mult is not None:
            perf_score = min(100.0, max(0.0, round(50.0 * views_mult, 2)))
        else:
            perf_score = None

        return CreatorBenchmark(
            has_sufficient_data=True,
            creator_reel_count=total_creator_reels,
            creator_avg_views=round(avg_views, 1) if avg_views else None,
            creator_avg_overall_rate=round(avg_rate, 3) if avg_rate else None,
            views_multiplier=round(views_mult, 2) if views_mult else None,
            rate_multiplier=round(rate_mult, 2) if rate_mult else None,
            performance_score=perf_score,
        )

    def score_reel(
        self,
        reel: ReelItem,
        all_reels: Optional[List[ReelItem]] = None,
        reference_time: Optional[datetime] = None
    ) -> ReelScoreBreakdown:
        """Scores a single ReelItem across all 5 dimensions and computes composite ranking metrics."""
        rates = self.calculate_rates(reel)
        popularity = self.calculate_popularity_score(reel)
        engagement = self.calculate_engagement_score(rates)
        recency, age_days = self.calculate_recency_score(reel.published_at, reference_time=reference_time)
        category, niche_relevance = self.calculate_niche_relevance_score(reel)

        # Creator Benchmark
        creator_benchmark = self.calculate_creator_benchmark(
            reel,
            creator_reels=all_reels or [reel],
            this_rates=rates
        )

        # Safe defaults for composite rankings when specific dimensions are missing:
        # If popularity is missing (e.g. no view/like counts), default to 0.0 in composite
        pop_val = popularity if popularity is not None else 0.0
        # If engagement is missing, default to 0.0 in composite
        eng_val = engagement if engagement is not None else 0.0
        # If recency is missing, default to neutral 50.0 (middle decay)
        rec_val = recency if recency is not None else 50.0

        # Composite Rankings:
        # 1. Most Popular = 65% Popularity + 20% Engagement + 15% Niche Relevance
        comp_popular = round(
            (pop_val * self.weights.rank_popular_pop_weight) +
            (eng_val * self.weights.rank_popular_eng_weight) +
            (niche_relevance * self.weights.rank_popular_niche_weight),
            2
        )

        # 2. Best Engagement = 60% Engagement + 20% Popularity + 20% Niche Relevance
        comp_engagement = round(
            (eng_val * self.weights.rank_eng_eng_weight) +
            (pop_val * self.weights.rank_eng_pop_weight) +
            (niche_relevance * self.weights.rank_eng_niche_weight),
            2
        )

        # 3. Rising Content = 40% Recency + 35% Engagement + 15% Popularity + 10% Niche Relevance
        comp_rising = round(
            (rec_val * self.weights.rank_rising_recency_weight) +
            (eng_val * self.weights.rank_rising_eng_weight) +
            (pop_val * self.weights.rank_rising_pop_weight) +
            (niche_relevance * self.weights.rank_rising_niche_weight),
            2
        )

        return ReelScoreBreakdown(
            reel_id=reel.reel_id,
            shortcode=reel.shortcode,
            author_username=reel.author_username,
            category=category,
            raw_views=reel.play_count,
            raw_likes=reel.like_count,
            raw_comments=reel.comment_count,
            raw_shares=reel.share_count,
            published_at=reel.published_at,
            age_in_days=age_days,
            popularity_score=popularity,
            engagement_score=engagement,
            recency_score=recency,
            niche_relevance_score=niche_relevance,
            rates=rates,
            creator_benchmark=creator_benchmark,
            composite_popular_score=comp_popular,
            composite_engagement_score=comp_engagement,
            composite_rising_score=comp_rising,
        )

    def deduplicate_reels(self, reels: List[ReelItem]) -> List[ReelItem]:
        """Eliminates duplicate Reel records by reel_id or shortcode, preserving the latest/richest."""
        seen_keys = set()
        deduped: List[ReelItem] = []

        for r in reels:
            # Primary key: reel_id; Secondary fallback: shortcode or url
            primary_key = (r.reel_id or "").strip()
            shortcode_key = (r.shortcode or "").strip()

            if primary_key and primary_key in seen_keys:
                continue
            if shortcode_key and shortcode_key in seen_keys:
                continue

            if primary_key:
                seen_keys.add(primary_key)
            if shortcode_key:
                seen_keys.add(shortcode_key)

            deduped.append(r)

        return deduped

    def rank_reels(
        self,
        reels: List[ReelItem],
        reference_time: Optional[datetime] = None
    ) -> Dict[str, List[ReelScoreBreakdown]]:
        """Processes a list of Reels and produces three ranked leaderboards:
        1. 'most_popular': Highest reach volume & social validation.
        2. 'best_engagement': Highest interaction depth per view.
        3. 'rising_content': Fresh recent reels with accelerating engagement.
        """
        deduped = self.deduplicate_reels(reels)
        scored = [self.score_reel(r, all_reels=deduped, reference_time=reference_time) for r in deduped]

        # 1. Most Popular ranking: sorted by composite_popular_score DESC
        most_popular = sorted(
            scored,
            key=lambda x: (x.composite_popular_score, x.popularity_score or 0.0, x.raw_views or 0),
            reverse=True
        )

        # 2. Best Engagement ranking: sorted by composite_engagement_score DESC
        best_engagement = sorted(
            scored,
            key=lambda x: (x.composite_engagement_score, x.engagement_score or 0.0, x.rates.overall_rate or 0.0),
            reverse=True
        )

        # 3. Rising Content ranking: sorted by composite_rising_score DESC
        rising_content = sorted(
            scored,
            key=lambda x: (x.composite_rising_score, x.recency_score or 0.0, x.engagement_score or 0.0),
            reverse=True
        )

        return {
            "most_popular": most_popular,
            "best_engagement": best_engagement,
            "rising_content": rising_content,
        }
