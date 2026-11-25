"""Instagram Hook & Format Intelligence Engine for AdSync Marketing.

Provides offline-first analysis of Instagram Reel hooks, psychological techniques,
video formats, storytelling structures, and call-to-action (CTA) patterns.

Core Analytical Capabilities:
1. Hook Analysis:
   - Evaluates opening lines for 10 distinct psychological archetypes:
     Curiosity Gap, Contrarian / Myth-Busting, Problem-Solution, Bold Claim,
     Question-Based, List-Based, Storytelling, Fear of Missing Out (FOMO),
     Social Proof, Educational / How-To.
   - Extracts opening hooks only where sufficient text exists; never claims to
     analyze spoken audio when transcripts are unavailable.
2. Video Format Classification:
   - Classifies formats across 10 categories: Talking Head, Screen Recording,
     Cinematic B-Roll, Text-Based Reel, Animation, Tutorial / Demonstration,
     Before and After, Interview / Podcast, Product Showcase, Mixed Format.
   - Assigns confidence and marks uncertain classifications appropriately.
3. Content Structure Analysis:
   - Identifies structural sections (Hook, Problem, Explanation, Demonstration,
     Proof / Example, Payoff, CTA) based on textual signposts; never fabricates
     missing sections.
4. Call-to-Action (CTA) Detection:
   - Identifies intended viewer action: Follow, Comment, Save, Share, DM,
     Click Link, Contact / Enquiry, No Clear CTA.
5. Performance Intelligence:
   - Correlates patterns with engagement and popularity scores.
   - Clearly separates correlation from causation.
6. AdSync Content Insights:
   - Generates niche-specific actionable recommendations for AdSync's 8 verticals
     to create original content rather than copy competitor material.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import re
from typing import List, Optional, Dict, Any, Tuple, Set

from ..storage.models import ReelItem
from .scoring import EngagementScoringEngine, ReelScoreBreakdown, ScoringWeights
from .categorization import classify_reel_category, CATEGORY_TAXONOMY


# 10 Supported Hook Categories
HOOK_CATEGORIES = [
    "Curiosity Gap",
    "Contrarian / Myth-Busting",
    "Problem-Solution",
    "Bold Claim",
    "Question-Based",
    "List-Based",
    "Storytelling",
    "Fear of Missing Out",
    "Social Proof",
    "Educational / How-To",
]

# 10 Supported Video Formats
VIDEO_FORMATS = [
    "Talking Head",
    "Screen Recording",
    "Cinematic B-Roll",
    "Text-Based Reel",
    "Animation",
    "Tutorial / Demonstration",
    "Before and After",
    "Interview / Podcast",
    "Product Showcase",
    "Mixed Format",
]

# 8 Supported CTA Types
CTA_TYPES = [
    "Follow",
    "Comment",
    "Save",
    "Share",
    "DM",
    "Click Link",
    "Contact / Enquiry",
    "No Clear CTA",
]


@dataclass
class HookDetail:
    """Detailed hook analysis for a Reel."""
    hook_text: str
    category: str
    confidence: float
    psychological_trigger: str
    is_extracted: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FormatDetail:
    """Classified content presentation format."""
    format_name: str
    confidence: float
    is_uncertain: bool
    evidence_cues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructureDetail:
    """Identified structural progression of the content."""
    detected_elements: List[str]  # e.g. ["Hook", "Problem", "Explanation", "Call to Action"]
    structure_flow: str           # e.g. "Hook -> Problem -> Explanation -> Call to Action"
    has_hook: bool
    has_problem: bool
    has_explanation: bool
    has_demonstration: bool
    has_proof: bool
    has_payoff: bool
    has_cta: bool
    completeness_score: float     # 0.0 to 100.0 based on how many structural elements exist

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CTADetail:
    """Detected call-to-action intent and phrase."""
    cta_type: str
    target_action: Optional[str]
    detected_phrase: Optional[str]
    has_clear_cta: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReelHookFormatAnalysis:
    """Complete Hook & Format Intelligence evaluation for a single Reel."""
    reel_id: str
    shortcode: str
    author_username: str
    niche_category: str
    has_sufficient_text: bool
    hook: HookDetail
    format: FormatDetail
    structure: StructureDetail
    cta: CTADetail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reel_id": self.reel_id,
            "shortcode": self.shortcode,
            "author_username": self.author_username,
            "niche_category": self.niche_category,
            "has_sufficient_text": self.has_sufficient_text,
            "hook": self.hook.to_dict(),
            "format": self.format.to_dict(),
            "structure": self.structure.to_dict(),
            "cta": self.cta.to_dict(),
        }


@dataclass
class PatternPerformanceReport:
    """Aggregated performance intelligence linking hooks, formats, and CTAs to engagement."""
    generated_at: str
    total_reels_analyzed: int
    most_common_hooks: List[Dict[str, Any]]
    best_performing_hooks: List[Dict[str, Any]]
    most_common_formats: List[Dict[str, Any]]
    best_performing_formats: List[Dict[str, Any]]
    cta_performance: List[Dict[str, Any]]
    high_performing_structures: List[Dict[str, Any]]
    competitor_pattern_differences: Dict[str, Any]
    correlation_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NicheContentRecommendation:
    """Actionable original production recommendation for an AdSync niche."""
    niche: str
    recommended_hook_categories: List[str]
    recommended_formats: List[str]
    recommended_cta_strategy: str
    recommended_structure: str
    sample_original_hook_templates: List[str]
    strategic_rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HookFormatIntelligenceEngine:
    """Orchestrates pattern recognition, psychological hook categorization,
    format detection, structural mapping, CTA analysis, and niche recommendations.
    """

    def __init__(self, scoring_weights: Optional[ScoringWeights] = None):
        self.scoring_engine = EngagementScoringEngine(weights=scoring_weights)

    # =========================================================================
    # 1. Opening Hook Analysis
    # =========================================================================

    def extract_opening_hook(self, caption: Optional[str]) -> Tuple[str, bool]:
        """Extracts the opening sentence/line from the caption.
        Returns (hook_text, is_extracted). If text is insufficient or empty,
        returns an honest placeholder without fabricating audio transcripts.
        """
        if not caption or not caption.strip():
            return "No text available (visual or audio only)", False

        clean_text = caption.strip()
        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        if not lines:
            return "No text available", False

        first_line = lines[0]
        # Strip leading decorative emojis or bullet points
        cleaned = re.sub(r"^[^\w\s\$\#\%\@\?]+", "", first_line).strip()
        final_line = cleaned if cleaned else first_line

        # If the first line is very short (e.g. 'Hey' or single emoji), consider second line
        if len(final_line) < 5 and len(lines) > 1:
            second_line = re.sub(r"^[^\w\s\$\#\%\@\?]+", "", lines[1]).strip()
            if len(second_line) >= 5:
                final_line = f"{final_line} {second_line}".strip()

        return final_line, True

    def classify_hook(self, hook_text: str, is_extracted: bool) -> HookDetail:
        """Classifies the opening hook into one of the 10 psychological archetypes."""
        if not is_extracted or not hook_text:
            return HookDetail(
                hook_text="No opening text available",
                category="Unknown / No Text",
                confidence=0.0,
                psychological_trigger="No textual transcript or caption hook available to evaluate.",
                is_extracted=False
            )

        lower = hook_text.lower()

        # 1. Fear of Missing Out (FOMO) - check before general Contrarian
        if any(k in lower for k in ["miss out", "ending soon", "don't miss", "dont miss", "while you still can", "before it's too late", "before its too late", "before meta bans", "before it gets banned"]):
            return HookDetail(
                hook_text=hook_text,
                category="Fear of Missing Out",
                confidence=0.92,
                psychological_trigger="Leverages loss aversion and temporal urgency to force immediate viewing.",
                is_extracted=True
            )

        # 2. Contrarian / Myth-Busting
        if any(k in lower for k in ["stop ", "never ", "dead", "don't ", "dont ", "kills", "ruining", "waste of", "worst mistake", "myth"]):
            return HookDetail(
                hook_text=hook_text,
                category="Contrarian / Myth-Busting",
                confidence=0.92,
                psychological_trigger="Disrupts autopilot scrolling by challenging an established belief or common bad habit.",
                is_extracted=True
            )

        # 2. Curiosity Gap
        if any(k in lower for k in ["secret", "nobody tells you", "what happens when", "the real reason", "quietly", "hidden trick", "insider"]):
            return HookDetail(
                hook_text=hook_text,
                category="Curiosity Gap",
                confidence=0.90,
                psychological_trigger="Creates an open cognitive loop that compels viewers to watch until the revelation.",
                is_extracted=True
            )

        # 3. List-Based
        if re.search(r"\b\d+\b", lower) and any(k in lower for k in ["ways", "reasons", "tools", "hacks", "steps", "rules", "mistakes", "tips"]):
            return HookDetail(
                hook_text=hook_text,
                category="List-Based",
                confidence=0.94,
                psychological_trigger="Sets structured cognitive expectations and lowers perceived consumption effort.",
                is_extracted=True
            )

        # 4. Educational / How-To
        if any(k in lower for k in ["how to ", "how we ", "tutorial", "step-by-step", "blueprint", "guide", "framework", "formula"]):
            return HookDetail(
                hook_text=hook_text,
                category="Educational / How-To",
                confidence=0.91,
                psychological_trigger="Promises actionable skills or practical takeaways that incentivize saving and reviewing.",
                is_extracted=True
            )

        # 5. Problem-Solution (Check before Question-Based so questions agitating problems are identified properly)
        if any(k in lower for k in ["struggling with", "tired of", "can't seem to", "cant seem to", "fix your", "problem with", "solves", "how to solve"]):
            return HookDetail(
                hook_text=hook_text,
                category="Problem-Solution",
                confidence=0.90,
                psychological_trigger="Agitates an active operational pain point before presenting a definitive remedy.",
                is_extracted=True
            )

        # 6. Question-Based
        if "?" in hook_text or lower.startswith(("why ", "are you ", "do you ", "what if ", "have you ", "can you ")):
            return HookDetail(
                hook_text=hook_text,
                category="Question-Based",
                confidence=0.88,
                psychological_trigger="Triggers reflexive mental processing and conversational micro-commitment.",
                is_extracted=True
            )

        # 7. Storytelling (Narrative markers take precedence over isolated dollar amounts)
        if any(k in lower for k in ["we were losing", "i spent", "in 2020", "last week my", "client walked in", "true story", "day in the life"]):
            return HookDetail(
                hook_text=hook_text,
                category="Storytelling",
                confidence=0.88,
                psychological_trigger="Engages episodic memory and narrative empathy to build viewer immersion.",
                is_extracted=True
            )

        # 8. Social Proof
        if any(k in lower for k in ["client", "doubled", "$", "0 to", "booked", "results", "case study", "benchmark", "from 10k to", "our agency"]):
            return HookDetail(
                hook_text=hook_text,
                category="Social Proof",
                confidence=0.89,
                psychological_trigger="Demonstrates credible verification and authority via verified numerical benchmarks.",
                is_extracted=True
            )

        # 9. Fear of Missing Out (FOMO)
        if any(k in lower for k in ["before it's too late", "before it gets banned", "miss out", "ending soon", "don't miss", "while you still can"]):
            return HookDetail(
                hook_text=hook_text,
                category="Fear of Missing Out",
                confidence=0.88,
                psychological_trigger="Leverages loss aversion and temporal urgency to force immediate viewing.",
                is_extracted=True
            )

        # 10. Bold Claim
        if any(k in lower for k in ["guarantee", "will change everything", "best ever", "impossible", "insane", "game changer", "revolutionary"]):
            return HookDetail(
                hook_text=hook_text,
                category="Bold Claim",
                confidence=0.86,
                psychological_trigger="Commands attention through an audacious, high-stakes value proposition.",
                is_extracted=True
            )

        # Default fallback: Curiosity Gap or Educational
        return HookDetail(
            hook_text=hook_text,
            category="Curiosity Gap",
            confidence=0.60,
            psychological_trigger="Invokes general interest or observation.",
            is_extracted=True
        )

    # =========================================================================
    # 2. Video Format Classification
    # =========================================================================

    def classify_format(self, reel: ReelItem) -> FormatDetail:
        """Infers presentation format based on textual cues, hashtags, audio cues, and style markers."""
        cap = (reel.caption or "").lower()
        tags = [t.lower() for t in reel.hashtags]
        all_text = f"{cap} {' '.join(tags)}"

        cues: List[str] = []

        # 1. Screen Recording
        if any(k in all_text for k in ["ads manager", "webhook", "notion", "crm", "workflow", "dashboard", "screen", "click here", "settings", "my screen"]):
            cues.append("Software UI / screen navigation cues")
            return FormatDetail("Screen Recording", 0.90, False, cues)

        # 2. Cinematic B-Roll
        if any(k in all_text for k in ["property", "home walkthrough", "neighborhood", "luxuryrealestate", "b-roll", "aesthetic", "cinematic", "drone"]):
            cues.append("Visual luxury/environment cues")
            return FormatDetail("Cinematic B-Roll", 0.88, False, cues)

        # 3. Before and After
        if any(k in all_text for k in ["before and after", "before vs after", "transformation", "rebrand", "makeover"]):
            cues.append("Transformation contrast markers")
            return FormatDetail("Before and After", 0.92, False, cues)

        # 4. Tutorial / Demonstration
        if any(k in all_text for k in ["step 1", "step 2", "tutorial", "demonstration", "watch how", "how to set up", "guide"]):
            cues.append("Procedural instructional steps")
            return FormatDetail("Tutorial / Demonstration", 0.89, False, cues)

        # 5. Interview / Podcast
        if any(k in all_text for k in ["podcast", "interview", "guest", "host", "clip from episode", "on the mic"]):
            cues.append("Audio interview or conversation cues")
            return FormatDetail("Interview / Podcast", 0.91, False, cues)

        # 6. Text-Based Reel
        if any(k in all_text for k in ["read caption", "slide", "carousel", "read below", "save this checklist", "text overlay"]):
            cues.append("Reading / text overlay prompt")
            return FormatDetail("Text-Based Reel", 0.85, False, cues)

        # 7. Product Showcase
        if any(k in all_text for k in ["unboxing", "product", "features", "specs", "packaging", "in the box"]):
            cues.append("Physical product display markers")
            return FormatDetail("Product Showcase", 0.86, False, cues)

        # 8. Animation
        if any(k in all_text for k in ["animated", "3d animation", "motion graphics", "infographic"]):
            cues.append("Graphic/animation notation")
            return FormatDetail("Animation", 0.85, False, cues)

        # 9. Talking Head (Self-narrative, client conversation)
        if any(k in all_text for k in ["i went", "my client said", "talking to you", "listen to this", "founder story"]):
            cues.append("Direct personal address")
            return FormatDetail("Talking Head", 0.75, False, cues)

        # Default fallback
        cues.append("General fast-paced visual explainer with mixed cues")
        return FormatDetail("Mixed Format", 0.50, True, cues)

    # =========================================================================
    # 3. Content Structure Analysis
    # =========================================================================

    def analyze_structure(self, caption: Optional[str]) -> StructureDetail:
        """Maps structural sections (Hook, Problem, Explanation, Demonstration, Proof, Payoff, CTA).
        Does not fabricate missing sections.
        """
        if not caption or not caption.strip():
            return StructureDetail(
                detected_elements=[],
                structure_flow="No textual structure available",
                has_hook=False,
                has_problem=False,
                has_explanation=False,
                has_demonstration=False,
                has_proof=False,
                has_payoff=False,
                has_cta=False,
                completeness_score=0.0
            )

        lower = caption.lower()
        elements: List[str] = []

        # 1. Hook (Opening sentence exists)
        has_hook = len(caption.strip()) >= 10
        if has_hook:
            elements.append("Hook")

        # 2. Problem
        has_problem = any(k in lower for k in ["mistake", "problem", "losing", "kills", "wrong", "struggling", "waste", "why your", "fatigue"])
        if has_problem:
            elements.append("Problem")

        # 3. Explanation
        has_explanation = any(k in lower for k in ["here's what", "heres why", "because", "the reason", "here is how", "here is why", "this means", "principle"])
        if has_explanation:
            elements.append("Explanation")

        # 4. Demonstration / Steps
        has_demonstration = any(k in lower for k in ["step 1", "step 2", "1.", "2.", "open ads manager", "first,", "second,", "click"])
        if has_demonstration:
            elements.append("Demonstration")

        # 5. Proof / Example
        has_proof = any(k in lower for k in ["for example", "e.g.", "case study", "$", "booked", "result", "client went from"])
        if has_proof:
            elements.append("Proof / Example")

        # 6. Payoff
        has_payoff = any(k in lower for k in ["now you can", "this allows you", "the outcome", "leads to", "profitable", "scale"])
        if has_payoff:
            elements.append("Payoff")

        # 7. Call to Action
        has_cta = any(k in lower for k in ["comment", "save", "share", "follow", "dm me", "link in bio", "click the link"])
        if has_cta:
            elements.append("Call to Action")

        flow = " -> ".join(elements) if elements else "Unstructured content"
        completeness = round((len(elements) / 7.0) * 100.0, 1)

        return StructureDetail(
            detected_elements=elements,
            structure_flow=flow,
            has_hook=has_hook,
            has_problem=has_problem,
            has_explanation=has_explanation,
            has_demonstration=has_demonstration,
            has_proof=has_proof,
            has_payoff=has_payoff,
            has_cta=has_cta,
            completeness_score=completeness
        )

    # =========================================================================
    # 4. Call-to-Action (CTA) Analysis
    # =========================================================================

    def analyze_cta(self, caption: Optional[str]) -> CTADetail:
        """Identifies specific CTA directives in the caption."""
        if not caption or not caption.strip():
            return CTADetail("No Clear CTA", None, None, False)

        lower = caption.lower()

        # 1. Comment CTA (e.g. Comment 'ADS')
        comment_match = re.search(r"\bcomment\s+['\"]?([a-z0-9_]+)['\"]?", lower)
        if comment_match:
            word = comment_match.group(1).upper()
            return CTADetail("Comment", f"Comment '{word}'", f"comment {word}", True)
        if "comment below" in lower or "leave a comment" in lower or "drop a comment" in lower:
            return CTADetail("Comment", "Discussion prompt", "comment below", True)

        # 2. DM CTA
        if any(k in lower for k in ["dm me", "send me a dm", "message me", "dm us"]):
            return CTADetail("DM", "Direct Message for inquiry/resource", "dm me", True)

        # 3. Save CTA
        if any(k in lower for k in ["save this", "save for later", "save to your"]):
            return CTADetail("Save", "Save reel to collection", "save this", True)

        # 4. Share CTA
        if any(k in lower for k in ["share this", "share with a friend", "send this to"]):
            return CTADetail("Share", "Share video with peer", "share this", True)

        # 5. Follow CTA
        if any(k in lower for k in ["follow for more", "follow @", "follow us", "follow for daily", "make sure to follow", "follow"]):
            return CTADetail("Follow", "Follow creator profile", "follow", True)

        # 6. Click Link CTA
        if any(k in lower for k in ["link in bio", "click the link", "check my bio", "tap the link"]):
            return CTADetail("Click Link", "External funnel / bio link", "link in bio", True)

        # 7. Contact / Enquiry CTA
        if any(k in lower for k in ["book a call", "schedule a consult", "contact our team", "apply now"]):
            return CTADetail("Contact / Enquiry", "High-ticket sales inquiry", "book a call", True)

        return CTADetail("No Clear CTA", None, None, False)

    # =========================================================================
    # 5. Unified Single-Reel Evaluation
    # =========================================================================

    def evaluate_reel(self, reel: ReelItem) -> ReelHookFormatAnalysis:
        """Performs end-to-end Hook & Format analysis on a single ReelItem."""
        caption = reel.caption or ""
        hook_text, is_extracted = self.extract_opening_hook(caption)
        hook_detail = self.classify_hook(hook_text, is_extracted)
        format_detail = self.classify_format(reel)
        structure_detail = self.analyze_structure(caption)
        cta_detail = self.analyze_cta(caption)
        niche_cat, _ = classify_reel_category(reel)

        return ReelHookFormatAnalysis(
            reel_id=reel.reel_id,
            shortcode=reel.shortcode,
            author_username=reel.author_username,
            niche_category=niche_cat,
            has_sufficient_text=is_extracted,
            hook=hook_detail,
            format=format_detail,
            structure=structure_detail,
            cta=cta_detail
        )

    # =========================================================================
    # 6. Performance Intelligence & Pattern Aggregation
    # =========================================================================

    def analyze_patterns_and_performance(
        self,
        reels: List[ReelItem]
    ) -> PatternPerformanceReport:
        """Connects hook categories, formats, and CTAs to engagement scores across a dataset."""
        scored_map: Dict[str, ReelScoreBreakdown] = {}
        for r in reels:
            scored_map[r.reel_id] = self.scoring_engine.score_reel(r, all_reels=reels)

        analyzed_list = [self.evaluate_reel(r) for r in reels]

        # Group metrics by hook category
        hook_groups: Dict[str, List[float]] = {}
        format_groups: Dict[str, List[float]] = {}
        cta_groups: Dict[str, List[float]] = {}
        structure_groups: Dict[str, List[float]] = {}
        competitor_patterns: Dict[str, Dict[str, int]] = {}

        for item in analyzed_list:
            bd = scored_map.get(item.reel_id)
            eng_score = bd.engagement_score if (bd and bd.engagement_score is not None) else 0.0

            # Hook aggregation
            h_cat = item.hook.category
            hook_groups.setdefault(h_cat, []).append(eng_score)

            # Format aggregation
            fmt = item.format.format_name
            format_groups.setdefault(fmt, []).append(eng_score)

            # CTA aggregation
            cta = item.cta.cta_type
            cta_groups.setdefault(cta, []).append(eng_score)

            # Structure flow aggregation
            flow = item.structure.structure_flow
            structure_groups.setdefault(flow, []).append(eng_score)

            # Competitor pattern aggregation
            creator = item.author_username.lower().strip()
            if creator not in competitor_patterns:
                competitor_patterns[creator] = {"hooks": {}, "formats": {}, "ctas": {}}
            c_entry = competitor_patterns[creator]
            c_entry["hooks"][h_cat] = c_entry["hooks"].get(h_cat, 0) + 1
            c_entry["formats"][fmt] = c_entry["formats"].get(fmt, 0) + 1
            c_entry["ctas"][cta] = c_entry["ctas"].get(cta, 0) + 1

        total = len(analyzed_list) or 1

        # Summary tables
        most_common_hooks = [
            {"category": cat, "count": len(scores), "share_pct": round((len(scores) / total) * 100, 1)}
            for cat, scores in sorted(hook_groups.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        best_performing_hooks = [
            {"category": cat, "avg_engagement_score": round(sum(scores) / len(scores), 2), "sample_count": len(scores)}
            for cat, scores in sorted(hook_groups.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
        ]

        most_common_formats = [
            {"format": fmt, "count": len(scores), "share_pct": round((len(scores) / total) * 100, 1)}
            for fmt, scores in sorted(format_groups.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        best_performing_formats = [
            {"format": fmt, "avg_engagement_score": round(sum(scores) / len(scores), 2), "sample_count": len(scores)}
            for fmt, scores in sorted(format_groups.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
        ]

        cta_performance = [
            {"cta_type": cta, "count": len(scores), "avg_engagement_score": round(sum(scores) / len(scores), 2)}
            for cta, scores in sorted(cta_groups.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
        ]

        high_performing_structures = [
            {"flow": flow, "count": len(scores), "avg_engagement_score": round(sum(scores) / len(scores), 2)}
            for flow, scores in sorted(structure_groups.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)[:5]
        ]

        return PatternPerformanceReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_reels_analyzed=len(reels),
            most_common_hooks=most_common_hooks,
            best_performing_hooks=best_performing_hooks,
            most_common_formats=most_common_formats,
            best_performing_formats=best_performing_formats,
            cta_performance=cta_performance,
            high_performing_structures=high_performing_structures,
            competitor_pattern_differences=competitor_patterns,
            correlation_disclaimer=(
                "Correlation Notice: High engagement scores associated with specific hooks or formats "
                "indicate positive observational correlation within current sample data, not direct causal "
                "guarantees of future performance. Algorithm distribution is multi-factorial."
            )
        )

    # =========================================================================
    # 7. AdSync Niche-Specific Recommendations
    # =========================================================================

    def get_niche_recommendations(self, niche: str) -> NicheContentRecommendation:
        """Generates actionable, original production blueprints for each of AdSync's 8 core marketing niches."""
        norm_niche = next((cat for cat in CATEGORY_TAXONOMY if cat.lower() == niche.lower()), None)
        if not norm_niche:
            norm_niche = "Digital Marketing"

        niche_blueprints: Dict[str, Dict[str, Any]] = {
            "Meta Ads": {
                "hooks": ["Contrarian / Myth-Busting", "Problem-Solution", "Social Proof"],
                "formats": ["Screen Recording", "Animation", "Tutorial / Demonstration"],
                "cta": "Comment 'AUDIT' to receive our free Advantage+ ad structure breakdown checklist.",
                "structure": "Hook -> Problem (Algorithm Trap) -> Explanation -> Demonstration (Ads Manager) -> Call to Action",
                "templates": [
                    "Why 80% of ad accounts are burning budget on 'Boost Post' instead of conversion routing.",
                    "The silent creative fatigue setting in Meta Ads Manager that doubles your CPA overnight.",
                    "Stop optimizing your ad sets for clicks if your actual goal is qualified consultation calls."
                ],
                "rationale": "Meta Ads audiences respond best to authoritative myth-busting backed by verified software screen breakdowns."
            },
            "Instagram Marketing": {
                "hooks": ["Curiosity Gap", "List-Based", "Contrarian / Myth-Busting"],
                "formats": ["Text-Based Reel", "Tutorial / Demonstration", "Talking Head"],
                "cta": "Save this reel to blueprint your video retention structure for your next shoot.",
                "structure": "Hook -> Problem (Audience Drop-off) -> Explanation -> Demonstration -> Payoff -> Call to Action",
                "templates": [
                    "The conflict-first hook formula that stops viewer scroll in under 2 seconds.",
                    "3 retention graph mistakes killing your Reels reach before second five.",
                    "Why starting your video with 'Hey guys' kills 70% of your audience retention instantly."
                ],
                "rationale": "Creators obsess over retention graphs and saveable frameworks; actionable structure drives exceptionally high save rates."
            },
            "Lead Generation": {
                "hooks": ["Problem-Solution", "Social Proof", "Educational / How-To"],
                "formats": ["Screen Recording", "Tutorial / Demonstration", "Before and After"],
                "cta": "DM us 'SYSTEM' to get the exact outbound funnel script template.",
                "structure": "Hook -> Problem (Dry Pipeline) -> Explanation -> Demonstration -> Proof -> Call to Action",
                "templates": [
                    "Why cold DMs get ignored and the 2-sentence conversational pivot that fixes it.",
                    "How an agency booked 24 qualified calls in 14 days without increasing ad spend.",
                    "The 3-stage inbound conversion mechanism for high-ticket service consultants."
                ],
                "rationale": "B2B and service founders want tangible lead conversion mechanisms; social proof and DM magnets drive qualified inquiries."
            },
            "Marketing Automation": {
                "hooks": ["Educational / How-To", "Problem-Solution", "Curiosity Gap"],
                "formats": ["Screen Recording", "Tutorial / Demonstration", "Animation"],
                "cta": "Comment 'WORKFLOW' for our pre-built CRM webhook onboarding blueprint.",
                "structure": "Hook -> Problem (Manual Bottleneck) -> Explanation -> Demonstration (Workflow Cutaway) -> Call to Action",
                "templates": [
                    "How to automate your client onboarding pipeline from lead form to paid invoice in 60 seconds.",
                    "The AI agent webhook workflow that responds to inbound inquiries in under 15 seconds.",
                    "Stop manually typing lead data between your CRM and calendar."
                ],
                "rationale": "Systems and operational efficiency are best communicated via visual workflow demonstrations and automated triggers."
            },
            "Branding": {
                "hooks": ["Storytelling", "Contrarian / Myth-Busting", "Bold Claim"],
                "formats": ["Cinematic B-Roll", "Talking Head", "Before and After"],
                "cta": "Follow for daily brand positioning strategies and identity breakdowns.",
                "structure": "Hook -> Problem (Commoditization) -> Explanation (Positioning) -> Payoff -> Call to Action",
                "templates": [
                    "Why competing on price guarantees your agency remains invisible and overworked.",
                    "How premium brands charge 5x market rates without changing their underlying product.",
                    "The positioning shift that turns generic freelance offers into category authority."
                ],
                "rationale": "Brand authority requires emotional resonance, contrarian positioning, and clean, high-production visual aesthetics."
            },
            "Business Growth": {
                "hooks": ["Storytelling", "Contrarian / Myth-Busting", "Social Proof"],
                "formats": ["Talking Head", "Text-Based Reel", "Tutorial / Demonstration"],
                "cta": "Save this breakdown and share it with your co-founder or operations lead.",
                "structure": "Hook -> Problem (Founder Bottleneck) -> Explanation -> Payoff -> Call to Action",
                "templates": [
                    "The revenue ceiling every agency hits at $30k/month and the operational shift needed to break it.",
                    "Why working 70 hours a week is an operational design flaw, not a badge of honor.",
                    "How we productized custom client engagements into scalable high-margin retainers."
                ],
                "rationale": "Founders respond to operational transparency, productization insights, and strategic scaling blueprints."
            },
            "Real Estate Marketing": {
                "hooks": ["Curiosity Gap", "Storytelling", "Problem-Solution"],
                "formats": ["Cinematic B-Roll", "Tutorial / Demonstration", "Before and After"],
                "cta": "Comment 'LISTING' for our cinematic property video script blueprint.",
                "structure": "Hook -> Problem (Boring Walkthroughs) -> Explanation -> Demonstration (Lifestyle Framing) -> Call to Action",
                "templates": [
                    "Why filming the kitchen island for 15 seconds will never sell a multi-million dollar property.",
                    "The lifestyle storytelling walkthrough format that attracted 3 cash buyers in one week.",
                    "How top residential brokers use 45-second architectural shorts to build private buyer lists."
                ],
                "rationale": "Property marketing requires cinematic lifestyle framing rather than static architectural tours."
            },
            "Digital Marketing": {
                "hooks": ["Educational / How-To", "List-Based", "Contrarian / Myth-Busting"],
                "formats": ["Screen Recording", "Text-Based Reel", "Tutorial / Demonstration"],
                "cta": "Save this reel and comment 'BLUEPRINT' for the full multichannel marketing strategy guide.",
                "structure": "Hook -> Problem -> Explanation -> Demonstration -> Call to Action",
                "templates": [
                    "The 3-channel attribution framework modern marketing teams use to measure true ROI.",
                    "Why relying on a single traffic source leaves your business vulnerable to algorithm shifts.",
                    "5 conversion rate optimization tweaks that lifted our funnel checkout by 34%."
                ],
                "rationale": "Actionable, multi-channel blueprints with clear analytical hooks deliver the strongest broad-audience engagement."
            }
        }

        bp = niche_blueprints[norm_niche]
        return NicheContentRecommendation(
            niche=norm_niche,
            recommended_hook_categories=bp["hooks"],
            recommended_formats=bp["formats"],
            recommended_cta_strategy=bp["cta"],
            recommended_structure=bp["structure"],
            sample_original_hook_templates=bp["templates"],
            strategic_rationale=bp["rationale"]
        )
