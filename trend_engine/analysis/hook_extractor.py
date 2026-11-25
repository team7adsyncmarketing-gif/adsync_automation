"""Hook extraction, content format classification, and engagement analysis."""

import re
from typing import Tuple, Dict, Any, Optional
from ..storage.models import ReelItem, ReelAnalysis
from .categorization import classify_reel_category


def extract_hook_sentence(caption: str) -> str:
    """Extracts the high-impact opening hook line or sentence from the caption."""
    if not caption:
        return "Untitled Reel"
    lines = [line.strip() for line in caption.split("\n") if line.strip()]
    if not lines:
        return caption[:100]
    first_line = lines[0]
    # Clean leading punctuation/emojis for readability
    clean = re.sub(r"^[^\w\s\$\#\%\@]+", "", first_line).strip()
    return clean if clean else first_line


def classify_hook_pattern(hook_text: str) -> Tuple[str, str]:
    """Identifies the psychological hook archetype and its persuasion trigger."""
    lower = hook_text.lower()

    if any(k in lower for k in ["stop ", "never ", "dead", "don't ", "dont ", "suicide", "kills"]):
        return (
            "Contrarian / Myth-Busting",
            "Disrupts autopilot scrolling by attacking a common sacred cow or established habit, forcing instant reassessment.",
        )
    if any(k in lower for k in ["real reason", "secret", "nobody tells you", "quietly", "what happens"]):
        return (
            "Curiosity Gap",
            "Creates an open cognitive loop that can only be closed by watching the video to the reveal.",
        )
    if any(k in lower for k in ["how we ", "how to ", "step", "formula", "framework", "method", "system"]):
        return (
            "Framework / Actionable Blueprint",
            "Promises a tangible, repeatable process that lowers perceived difficulty and drives high save rates.",
        )
    if any(k in lower for k in ["doubled", "$", "0 to", "booked", "resurrected", "test result", "benchmark"]):
        return (
            "Case Study / Proven Results",
            "Establishes immediate authority and credibility through verifiable numerical metrics and documented proof.",
        )
    if any(k in lower for k in ["why 90%", "if you're", "if your", "why your", "mistake", "warning", "fatigue"]):
        return (
            "Diagnostic / Problem-Agitation",
            "Speaks directly to a painful operational symptom, making the viewer feel specifically targeted and understood.",
        )

    return (
        "Insight / Provocative Question",
        "Engages intellectual curiosity through an assertive industry observation or high-stakes question.",
    )


def identify_content_format(reel: ReelItem) -> str:
    """Infers the visual presentation format based on text cues, audio, and style markers."""
    cap = reel.caption.lower()
    if any(k in cap for k in ["open ads manager", "webhook", "notion", "crm", "workflow", "screen", "click", "settings"]):
        return "Screen Recording / Workflow Breakdown"
    if any(k in cap for k in ["property", "home", "neighborhood", "walkthrough", "kitchen", "listing"]):
        return "Cinematic B-Roll Walkthrough"
    if any(k in cap for k in ["carousel", "slide 2", "read below", "save this", "checklist"]):
        return "Text Overlay / Kinetic Typography"
    if any(k in cap for k in ["how we went", "we were losing", "i spent", "client said"]):
        return "Direct Storytelling / Talking Head"
    return "Fast-Paced Explainer with On-Screen Graphics"


def compute_virality_score(reel: ReelItem) -> Optional[float]:
    """Calculates normalized virality index (0-100) emphasizing shares and comments.
    Returns None if all engagement metrics are missing/null, avoiding fabricated virality scores.
    """
    if (
        reel.play_count is None
        and reel.like_count is None
        and reel.comment_count is None
        and reel.share_count is None
    ):
        return None

    plays = reel.play_count if (reel.play_count is not None and reel.play_count > 0) else 1000
    likes = reel.like_count or 0
    comments = reel.comment_count or 0
    shares = reel.share_count or 0

    # Heavy algorithmic weighting: shares (4x), comments (2.5x), likes (1x)
    weighted_interactions = likes + (comments * 2.5) + (shares * 4.0)
    raw_rate = (weighted_interactions / plays) * 100.0

    # Logarithmic-like scaling between 40.0 and 99.0 for clear rankability
    base_score = min(99.0, max(45.0, round(raw_rate * 4.2 + 35.0, 1)))
    return base_score


def analyze_reel(reel: ReelItem) -> ReelAnalysis:
    """Performs full trend analysis on a ReelItem."""
    category, confidence = classify_reel_category(reel)
    hook_text = extract_hook_sentence(reel.caption)
    hook_type, hook_psychology = classify_hook_pattern(hook_text)
    content_format = identify_content_format(reel)
    virality_score = compute_virality_score(reel)

    return ReelAnalysis(
        reel_id=reel.reel_id,
        primary_category=category,
        confidence_score=confidence,
        hook_text=hook_text,
        hook_type=hook_type,
        hook_psychology=hook_psychology,
        content_format=content_format,
        virality_score=virality_score,
    )

