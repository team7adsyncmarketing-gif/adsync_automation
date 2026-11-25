"""Instagram Trending Detection Engine for AdSync Marketing.

Analyzes collected ReelItem records and their EngagementScoringEngine results to detect:
1. Popular content (broad reach & social proof)
2. Rising content (recent publication + accelerating momentum)
3. High-engagement content (deep audience interaction & share ratios)
4. Creator outperformance (reels significantly exceeding the creator's historical baseline)
5. Emerging topics (cross-creator repeated concepts with independent validation)
6. Niche-specific trends (categorized breakdowns across AdSync's 8 core marketing verticals)

Key Architectural & Mathematical Safeguards:
- Distinguishes historical popularity from recent momentum: high lifetime views alone
  never qualify an old Reel as currently trending.
- Calculates a configurable Trending Score (0–100) using multi-factor momentum weighting.
- Cross-creator validation: identifies repeated topics only across independent creators;
  repeated posts by the same creator are never counted as independent multi-creator confirmation.
- Handles insufficient data explicitly: missing timestamps, missing view counts, or single snapshots
  never invent fabricated growth velocity or virality claims.
- Provides human-readable explanations detailing why a Reel or topic is classified as trending.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import math
import re
from typing import List, Optional, Dict, Any, Tuple, Set
from ..storage.models import ReelItem
from .scoring import (
    EngagementScoringEngine,
    ScoringWeights,
    ReelScoreBreakdown,
    EngagementRates,
    CreatorBenchmark,
)
from .categorization import classify_reel_category, CATEGORY_TAXONOMY


@dataclass
class TrendingEngineConfig:
    """Configurable weights and thresholds for trending detection."""
    # Weights for Reel Trending Score (0-100)
    # Emphasizes recent momentum (recency) and interaction quality over sheer historical reach
    trend_recency_weight: float = 0.40
    trend_engagement_weight: float = 0.30
    trend_popularity_weight: float = 0.15
    trend_creator_outperf_weight: float = 0.15

    # Thresholds for classification badges
    rising_min_score: float = 65.0
    rising_max_age_days: float = 14.0
    high_engagement_min_rate: float = 8.0     # overall interaction rate >= 8%
    high_engagement_min_score: float = 70.0
    popular_min_views: int = 500_000
    popular_min_score: float = 75.0
    creator_outperf_multiplier: float = 1.75  # 75% higher views or engagement than creator baseline

    # Minimum independent creators required to confirm an emerging topic
    min_independent_creators: int = 2

    # Common stopwords ignored during topic keyword extraction
    stopwords: Set[str] = field(default_factory=lambda: {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by",
        "is", "it", "this", "that", "how", "what", "why", "when", "where", "who", "your",
        "you", "we", "our", "my", "i", "if", "not", "no", "can", "do", "from", "reels",
        "video", "watch", "post", "comment", "link", "bio", "save", "share", "follow",
        "here", "there", "just", "get", "make", "new", "all", "out", "about", "more"
    })


@dataclass
class TrendingReelResult:
    """Evaluated trending assessment for a single Instagram Reel."""
    reel_id: str
    shortcode: str
    author_username: str
    category: str
    published_at: Optional[str]
    age_in_days: Optional[float]

    # Metrics
    views: Optional[int]
    likes: Optional[int]
    comments: Optional[int]
    shares: Optional[int]
    overall_engagement_rate: Optional[float]

    # Scores
    trending_score: float
    popularity_score: Optional[float]
    engagement_score: Optional[float]
    recency_score: Optional[float]
    creator_performance_score: Optional[float]

    # Badges / Classifications
    is_trending: bool
    is_rising: bool
    is_high_engagement: bool
    is_popular: bool
    is_creator_outperformer: bool

    # Explanations & Status
    has_sufficient_data: bool
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmergingTopicCluster:
    """A topic/concept validated across independent creator reels."""
    topic_key: str
    topic_label: str
    category: str
    independent_creator_count: int
    creators: List[str]
    reels_count: int
    sample_reel_ids: List[str]
    sample_shortcodes: List[str]
    avg_trending_score: float
    total_views: Optional[int]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendingAnalysisReport:
    """Full trending assessment report across categories, topics, and rankings."""
    generated_at: str
    total_reels_evaluated: int
    deduplicated_reels_count: int
    trending_reels: List[TrendingReelResult]
    emerging_topics: List[EmergingTopicCluster]
    niche_trends: Dict[str, List[TrendingReelResult]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_reels_evaluated": self.total_reels_evaluated,
            "deduplicated_reels_count": self.deduplicated_reels_count,
            "trending_reels": [r.to_dict() for r in self.trending_reels],
            "emerging_topics": [t.to_dict() for t in self.emerging_topics],
            "niche_trends": {
                cat: [r.to_dict() for r in items]
                for cat, items in self.niche_trends.items()
            },
        }


class TrendingDetectionEngine:
    """Orchestrates trending detection, momentum calculation, and topic clustering."""

    def __init__(
        self,
        config: Optional[TrendingEngineConfig] = None,
        scoring_weights: Optional[ScoringWeights] = None
    ):
        self.config = config or TrendingEngineConfig()
        self.scoring_engine = EngagementScoringEngine(weights=scoring_weights)

    def calculate_trending_score(
        self,
        score_breakdown: ReelScoreBreakdown
    ) -> Tuple[float, bool, str]:
        """Calculates a Trending Score (0–100) and human-readable explanation.
        
        Formula:
          Trending Score =
            w_recency * Recency_Score +
            w_engagement * Engagement_Score +
            w_popularity * Popularity_Score +
            w_creator * Creator_Outperformance_Score
        
        Crucial Momentum Guard:
          If content is older than rising_max_age_days (or has very low recency score),
          high lifetime views alone will not elevate it to 'Currently Trending'.
          Recency actively gates the score.
        """
        reasons: List[str] = []
        has_sufficient_data = True

        rec = score_breakdown.recency_score
        eng = score_breakdown.engagement_score
        pop = score_breakdown.popularity_score
        bench = score_breakdown.creator_benchmark

        # Check for insufficient data cases
        if rec is None and pop is None and eng is None:
            return 0.0, False, "Insufficient data: All metric counts and timestamps are missing."

        if rec is None:
            has_sufficient_data = False
            rec_val = 30.0  # conservative penalty for unknown publish date
            reasons.append("Publication date unknown (momentum estimated conservatively).")
        else:
            rec_val = rec
            if score_breakdown.age_in_days is not None:
                if score_breakdown.age_in_days <= 3.0:
                    reasons.append(f"High recent momentum ({score_breakdown.age_in_days:.1f} days old).")
                elif score_breakdown.age_in_days > self.config.rising_max_age_days:
                    reasons.append(f"Older content ({score_breakdown.age_in_days:.1f} days old); historical reach discounted.")

        pop_val = pop if pop is not None else 0.0
        eng_val = eng if eng is not None else 0.0

        if eng is not None and score_breakdown.rates.overall_rate is not None:
            if score_breakdown.rates.overall_rate >= self.config.high_engagement_min_rate:
                reasons.append(f"Strong engagement rate of {score_breakdown.rates.overall_rate:.1f}%.")

        if pop is not None and score_breakdown.raw_views is not None:
            if score_breakdown.raw_views >= self.config.popular_min_views:
                reasons.append(f"Broad reach volume ({score_breakdown.raw_views:,} views).")

        # Creator outperformance factor (0-100)
        if bench.has_sufficient_data and bench.performance_score is not None:
            creator_val = bench.performance_score
            if bench.views_multiplier and bench.views_multiplier >= self.config.creator_outperf_multiplier:
                reasons.append(f"Outperformed creator baseline by {bench.views_multiplier:.1f}x views.")
            elif bench.rate_multiplier and bench.rate_multiplier >= self.config.creator_outperf_multiplier:
                reasons.append(f"Outperformed creator baseline by {bench.rate_multiplier:.1f}x engagement.")
        else:
            # When creator history is insufficient, fallback gracefully to neutral baseline
            creator_val = eng_val

        # Calculate weighted composite trending score
        raw_score = (
            (rec_val * self.config.trend_recency_weight) +
            (eng_val * self.config.trend_engagement_weight) +
            (pop_val * self.config.trend_popularity_weight) +
            (creator_val * self.config.trend_creator_outperf_weight)
        )

        # Older content momentum ceiling: If age > 21 days, cap trending score at 60.0
        # to ensure historical popularity cannot pose as current trending momentum
        if score_breakdown.age_in_days is not None and score_breakdown.age_in_days > 21.0:
            raw_score = min(60.0, raw_score)

        final_score = round(min(100.0, max(0.0, raw_score)), 2)

        explanation = " ".join(reasons) if reasons else "Standard baseline engagement."
        return final_score, has_sufficient_data, explanation

    def evaluate_reel(
        self,
        reel: ReelItem,
        all_reels: Optional[List[ReelItem]] = None,
        reference_time: Optional[datetime] = None
    ) -> TrendingReelResult:
        """Evaluates a single ReelItem, computing its trending score and classifications."""
        score_bd = self.scoring_engine.score_reel(reel, all_reels=all_reels, reference_time=reference_time)
        trending_score, has_data, explanation = self.calculate_trending_score(score_bd)

        # Classifications
        is_popular = (
            score_bd.raw_views is not None and
            score_bd.raw_views >= self.config.popular_min_views and
            (score_bd.popularity_score or 0.0) >= self.config.popular_min_score
        )

        is_high_eng = (
            score_bd.rates.overall_rate is not None and
            score_bd.rates.overall_rate >= self.config.high_engagement_min_rate and
            (score_bd.engagement_score or 0.0) >= self.config.high_engagement_min_score
        )

        age = score_bd.age_in_days
        is_rising = (
            trending_score >= self.config.rising_min_score and
            age is not None and age <= self.config.rising_max_age_days and
            (score_bd.engagement_score or 0.0) >= 50.0
        )

        bench = score_bd.creator_benchmark
        is_creator_outperformer = (
            bench.has_sufficient_data and
            ((bench.views_multiplier or 0.0) >= self.config.creator_outperf_multiplier or
             (bench.rate_multiplier or 0.0) >= self.config.creator_outperf_multiplier)
        )

        # Overall 'is_trending': must have high trending score AND either be rising or outperforming
        is_trending = (trending_score >= 65.0) and (is_rising or is_creator_outperformer or is_high_eng)

        return TrendingReelResult(
            reel_id=reel.reel_id,
            shortcode=reel.shortcode,
            author_username=reel.author_username,
            category=score_bd.category,
            published_at=reel.published_at,
            age_in_days=score_bd.age_in_days,
            views=reel.play_count,
            likes=reel.like_count,
            comments=reel.comment_count,
            shares=reel.share_count,
            overall_engagement_rate=score_bd.rates.overall_rate,
            trending_score=trending_score,
            popularity_score=score_bd.popularity_score,
            engagement_score=score_bd.engagement_score,
            recency_score=score_bd.recency_score,
            creator_performance_score=bench.performance_score,
            is_trending=is_trending,
            is_rising=is_rising,
            is_high_engagement=is_high_eng,
            is_popular=is_popular,
            is_creator_outperformer=is_creator_outperformer,
            has_sufficient_data=has_data,
            explanation=explanation,
        )

    def extract_topic_tokens(self, reel: ReelItem) -> Set[str]:
        """Extracts normalized key topic phrases/tokens from caption and hashtags."""
        corpus = f"{reel.caption.lower()} {' '.join(reel.hashtags).lower()}"
        words = re.findall(r"[a-z0-9\+\_]{3,}", corpus)
        meaningful = {
            w for w in words
            if w not in self.config.stopwords
            and not w.isdigit()
            and len(w) >= 3
        }
        return meaningful

    def detect_emerging_topics(
        self,
        reels: List[ReelItem],
        evaluated_reels: List[TrendingReelResult]
    ) -> List[EmergingTopicCluster]:
        """Clusters repeated topics and concepts across independent creators.
        
        Crucial Multi-Creator Guard:
          Does not count duplicate reels or repeatedly count the same creator
          as multiple independent confirmations. A topic must be produced by
          at least `min_independent_creators` (default 2) different creators.
        """
        score_map = {r.reel_id: r for r in evaluated_reels}

        # Map token -> Dict[creator, List[ReelItem]]
        token_creator_map: Dict[str, Dict[str, List[ReelItem]]] = {}

        for reel in reels:
            creator = (reel.author_username or "").strip().lower()
            if not creator:
                continue

            tokens = self.extract_topic_tokens(reel)
            for token in tokens:
                if token not in token_creator_map:
                    token_creator_map[token] = {}
                if creator not in token_creator_map[token]:
                    token_creator_map[token][creator] = []
                token_creator_map[token][creator].append(reel)

        # Filter topics that meet minimum independent creator threshold
        topic_clusters: List[EmergingTopicCluster] = []

        for token, creator_dict in token_creator_map.items():
            independent_creators = list(creator_dict.keys())
            if len(independent_creators) < self.config.min_independent_creators:
                continue

            all_cluster_reels: List[ReelItem] = []
            for c_reels in creator_dict.values():
                all_cluster_reels.extend(c_reels)

            sample_ids = [r.reel_id for r in all_cluster_reels[:5]]
            sample_codes = [r.shortcode for r in all_cluster_reels[:5]]

            # Determine dominant category for this topic cluster
            cat_counts: Dict[str, int] = {}
            total_views = 0
            has_any_views = False
            trending_scores = []

            for r in all_cluster_reels:
                res = score_map.get(r.reel_id)
                if res:
                    cat = res.category
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
                    trending_scores.append(res.trending_score)
                    if res.views is not None:
                        total_views += res.views
                        has_any_views = True

            best_category = max(cat_counts, key=cat_counts.get) if cat_counts else "Digital Marketing"
            avg_score = round(sum(trending_scores) / len(trending_scores), 2) if trending_scores else 50.0

            explanation = (
                f"Validated across {len(independent_creators)} independent creators "
                f"({', '.join(independent_creators[:3])}) across {len(all_cluster_reels)} reels."
            )

            topic_clusters.append(EmergingTopicCluster(
                topic_key=token,
                topic_label=token.replace("_", " ").title(),
                category=best_category,
                independent_creator_count=len(independent_creators),
                creators=independent_creators,
                reels_count=len(all_cluster_reels),
                sample_reel_ids=sample_ids,
                sample_shortcodes=sample_codes,
                avg_trending_score=avg_score,
                total_views=total_views if has_any_views else None,
                explanation=explanation,
            ))

        # Sort clusters by independent creator count DESC, then avg_trending_score DESC
        topic_clusters.sort(
            key=lambda t: (t.independent_creator_count, t.avg_trending_score, t.reels_count),
            reverse=True
        )

        return topic_clusters

    def analyze_dataset(
        self,
        reels: List[ReelItem],
        reference_time: Optional[datetime] = None
    ) -> TrendingAnalysisReport:
        """Executes full trending intelligence analysis over a list of ReelItem objects.
        
        Steps:
        1. Deduplicates reels by reel_id and shortcode.
        2. Evaluates trending scores and badges for each reel.
        3. Identifies cross-creator emerging topic clusters.
        4. Partitions results into niche-specific trend leaderboards across AdSync's 8 categories.
        """
        deduped = self.scoring_engine.deduplicate_reels(reels)
        evaluated = [
            self.evaluate_reel(r, all_reels=deduped, reference_time=reference_time)
            for r in deduped
        ]

        # Sort trending reels by trending_score DESC
        evaluated.sort(key=lambda x: (x.trending_score, x.overall_engagement_rate or 0.0), reverse=True)

        # Detect emerging multi-creator topics
        emerging_topics = self.detect_emerging_topics(deduped, evaluated)

        # Partition into niche trends
        niche_trends: Dict[str, List[TrendingReelResult]] = {cat: [] for cat in CATEGORY_TAXONOMY}
        niche_trends["Other / Irrelevant"] = []

        for item in evaluated:
            cat = item.category
            if cat in niche_trends:
                niche_trends[cat].append(item)
            else:
                niche_trends["Other / Irrelevant"].append(item)

        return TrendingAnalysisReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_reels_evaluated=len(reels),
            deduplicated_reels_count=len(deduped),
            trending_reels=evaluated,
            emerging_topics=emerging_topics,
            niche_trends=niche_trends,
        )
