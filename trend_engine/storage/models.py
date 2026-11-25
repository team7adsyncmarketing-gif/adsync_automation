"""Data models for AdSync Trend Engine."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import json


@dataclass
class ReelItem:
    reel_id: str
    shortcode: str
    url: str
    caption: str
    author_username: str
    author_full_name: Optional[str] = None
    play_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    hashtags: List[str] = field(default_factory=list)
    audio_id: Optional[str] = None
    audio_title: Optional[str] = None
    audio_artist: Optional[str] = None
    is_original_audio: bool = False
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_mock: bool = False
    raw_json: Optional[str] = None

    @property
    def engagement_rate(self) -> Optional[float]:
        """Calculates engagement rate percentage: (likes + comments + shares) / plays.
        Returns None when play_count is unavailable, avoiding fabricated metric assumptions.
        """
        if self.play_count is not None and self.play_count > 0:
            likes = self.like_count or 0
            comments = self.comment_count or 0
            shares = self.share_count or 0
            rate = ((likes + comments + shares) / self.play_count) * 100.0
            return round(rate, 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["engagement_rate"] = self.engagement_rate
        return d


@dataclass
class ReelAnalysis:
    reel_id: str
    primary_category: str
    confidence_score: float
    hook_text: str
    hook_type: str
    hook_psychology: str
    content_format: str
    virality_score: Optional[float] = None
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdSyncIdea:
    idea_id: str
    source_reel_id: Optional[str]
    target_category: str
    topic: str
    hooks: List[str]
    target_audience: str
    business_problem: str
    content_format: str
    faceless_short_style: str
    call_to_action: str
    opportunity_score: float
    reasoning: str
    trend_reference_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompetitorProfile:
    handle: str
    category: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    verified: bool = False
    is_private: bool = False
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None
    added_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_fetched_at: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReelSnapshot:
    snapshot_id: str
    reel_id: str
    handle: str
    captured_at: str
    play_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



