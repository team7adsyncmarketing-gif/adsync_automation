"""Analysis module exports."""

from .categorization import classify_reel_category
from .hook_extractor import (
    extract_hook_sentence,
    classify_hook_pattern,
    identify_content_format,
    compute_virality_score,
    analyze_reel,
)
from .idea_generator import generate_adsync_idea, generate_batch_ideas
from .scoring import (
    ScoringWeights,
    EngagementRates,
    CreatorBenchmark,
    ReelScoreBreakdown,
    EngagementScoringEngine,
)
from .trending import (
    TrendingEngineConfig,
    TrendingReelResult,
    EmergingTopicCluster,
    TrendingAnalysisReport,
    TrendingDetectionEngine,
)
from .competitors import (
    COMPETITOR_CATEGORIES,
    CompetitorPerformanceSummary,
    CompetitorComparisonReport,
    CompetitorIntelligenceEngine,
)
from .hook_format import (
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
from .creative_director import (
    VALID_STYLES,
    VALID_VOICES,
    VALID_MUSIC,
    CreativeDecision,
    ScenePlan,
    CreativeBrief,
    AICreativeDirector,
)

__all__ = [
    "classify_reel_category",
    "extract_hook_sentence",
    "classify_hook_pattern",
    "identify_content_format",
    "compute_virality_score",
    "analyze_reel",
    "generate_adsync_idea",
    "generate_batch_ideas",
    "ScoringWeights",
    "EngagementRates",
    "CreatorBenchmark",
    "ReelScoreBreakdown",
    "EngagementScoringEngine",
    "TrendingEngineConfig",
    "TrendingReelResult",
    "EmergingTopicCluster",
    "TrendingAnalysisReport",
    "TrendingDetectionEngine",
    "COMPETITOR_CATEGORIES",
    "CompetitorPerformanceSummary",
    "CompetitorComparisonReport",
    "CompetitorIntelligenceEngine",
    "HOOK_CATEGORIES",
    "VIDEO_FORMATS",
    "CTA_TYPES",
    "HookDetail",
    "FormatDetail",
    "StructureDetail",
    "CTADetail",
    "ReelHookFormatAnalysis",
    "PatternPerformanceReport",
    "NicheContentRecommendation",
    "HookFormatIntelligenceEngine",
    "VALID_STYLES",
    "VALID_VOICES",
    "VALID_MUSIC",
    "CreativeDecision",
    "ScenePlan",
    "CreativeBrief",
    "AICreativeDirector",
]

