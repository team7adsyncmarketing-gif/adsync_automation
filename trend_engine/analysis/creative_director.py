"""AdSync AI Creative Director (Stage 8).

Translates marketing intelligence signals or user-provided topic briefs into
production-ready Faceless Shorts project specifications.

Key Capabilities:
1. Two Creation Modes:
   - MODE A (Intelligence-Driven): Auto-generates high-converting concepts from
     TrendingDetectionEngine, CompetitorIntelligenceEngine, and HookFormatIntelligenceEngine.
   - MODE B (User-Provided Brief): Parses natural-language user descriptions (e.g.
     "Create a 45-second Reel explaining why businesses get Instagram views but no customers..."),
     intelligently determining target audience, tone, duration, hook, style, voice, and CTA.
2. Structured Creative Decisions:
   - Selects duration, audience, tone, hook category, script structure, visual treatment,
     transitions, caption styles, voice, pace, and background music.
   - Uses sensible defaults when preferences are unspecified.
   - Only selects valid voices (`am_michael`, `am_puck`, `af_bella`, `af_nicole`, `bm_george`, etc.)
     and audio tracks (`bed`, `tension`, `bounce`, `none`) supported by the rendering engine.
3. Script Generation & Speaking Pace Calibration:
   - Composes structured scripts (Hook, Problem, Explanation, Demonstration/Proof, Payoff, CTA).
   - Calibrates line count and word count to target duration based on speaking pace (words/sec).
4. Scene Planning:
   - Breaks scripts into individual scenes with narration, visual description, on-screen caps,
     duration estimates, visual direction, transitions, and style tags.
5. Faceless Shorts Compatibility:
   - Generates exact `script.json` payloads compatible with the Phase 1 rendering engine.
   - Saves structured `CreativeBrief` packages in dedicated project output directories.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import uuid
from typing import List, Optional, Dict, Any, Tuple

from ..storage.models import ReelItem
from .scoring import EngagementScoringEngine, ScoringWeights
from .trending import TrendingDetectionEngine, TrendingEngineConfig, TrendingAnalysisReport
from .competitors import CompetitorIntelligenceEngine, CompetitorComparisonReport
from .hook_format import (
    HookFormatIntelligenceEngine,
    NicheContentRecommendation,
    HOOK_CATEGORIES,
    VIDEO_FORMATS,
    CTA_TYPES,
)
from .categorization import classify_reel_category, CATEGORY_TAXONOMY


# Supported Faceless Shorts Rendering Styles
VALID_STYLES = [
    "stick-story",   # Survival steps, 'what would you do if', gold step cards
    "deep-dive",     # 3D algorithmic mechanism & data flow
    "inside-out",    # Flat 2D x-ray cutaway explainer
    "tall-tale",     # Storytime breakdown, loophole, funny scaling lesson
    "paper-atlas",   # Regional maps, territory journey
    "night-file",    # Unsolved mystery, dark dramatic set
]

# Supported Kokoro TTS Voices
VALID_VOICES = [
    "am_michael",    # Male, authoritative, corporate/informative
    "am_puck",       # Male, energetic, conversational
    "af_bella",      # Female, warm, engaging
    "af_nicole",     # Female, professional, polished
    "bm_george",     # British Male, formal, articulate
    "bf_emma",       # British Female, crisp, modern
]

# Supported Music Beds
VALID_MUSIC = [
    "bed",           # Standard procedural upbeat/neutral background bed
    "tension",       # Suspenseful, dramatic pulse
    "bounce",        # Playful, light rhythmic pulse
    "none",          # No background track
]


@dataclass
class CreativeDecision:
    """Creative parameter decisions chosen by the AI Creative Director."""
    topic: str
    target_category: str
    target_audience: str
    tone: str
    target_duration: int          # target seconds (e.g. 30, 45, 60)
    estimated_duration: float     # estimated seconds from script word count
    hook_category: str
    script_structure: str
    video_style: str              # Faceless Shorts style key
    voice: str                    # Kokoro voice ID
    speaking_pace: float          # words per second (default 2.4 - 2.8)
    music: str                    # music track ID
    visual_treatment: str
    scene_transition: str
    caption_style: str
    call_to_action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScenePlan:
    """Detailed scene specification for video production."""
    scene_number: int
    narration_text: str
    on_screen_caps: str           # bold on-screen sync caption format e.g. "STEP *ONE: | AUDIT ADS"
    visual_description: str
    visual_direction: str
    transition: str
    estimated_duration: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CreativeBrief:
    """Complete, self-contained creative brief and rendering package."""
    brief_id: str
    creation_mode: str            # 'mode_a_intelligence' or 'mode_b_user_topic'
    created_at: str
    topic: str
    decisions: CreativeDecision
    script_lines: List[Dict[str, str]]
    scene_plans: List[ScenePlan]
    rendering_config: Dict[str, Any]
    project_directory: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "creation_mode": self.creation_mode,
            "created_at": self.created_at,
            "topic": self.topic,
            "decisions": self.decisions.to_dict(),
            "script_lines": self.script_lines,
            "scene_plans": [s.to_dict() for s in self.scene_plans],
            "rendering_config": self.rendering_config,
            "project_directory": self.project_directory,
        }


class AICreativeDirector:
    """Orchestrates content planning, natural language brief comprehension,
    script generation, and Faceless Shorts project assembly.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        scoring_weights: Optional[ScoringWeights] = None
    ):
        self.output_dir = Path(output_dir) if output_dir else Path("output/shorts_projects")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hook_engine = HookFormatIntelligenceEngine(scoring_weights=scoring_weights)
        self.trending_engine = TrendingDetectionEngine(scoring_weights=scoring_weights)

    # =========================================================================
    # 1. Mode B: User-Provided Topic Comprehension
    # =========================================================================

    def parse_user_prompt(self, prompt: str) -> Dict[str, Any]:
        """Extracts parameters from a natural-language brief using regex cues and fallbacks."""
        lower = prompt.lower()

        # Duration extraction (e.g., '45-second', '30s', '60 seconds', '1 minute')
        duration = 35  # default duration
        dur_match = re.search(r"\b(\d{1,3})\s*(?:-?\s*sec(?:ond)?s?|s)\b", lower)
        if dur_match:
            duration = int(dur_match.group(1))
        elif "1 minute" in lower or "60 sec" in lower:
            duration = 60
        elif "30 sec" in lower or "30s" in lower:
            duration = 30
        elif "45 sec" in lower or "45s" in lower:
            duration = 45

        # Category mapping from taxonomy keywords
        matched_cat = "Instagram Marketing"
        best_score = 0
        for cat, kws in CATEGORY_TAXONOMY.items():
            score = sum(1 for kw in kws if kw in lower)
            if score > best_score:
                best_score = score
                matched_cat = cat

        # Tone / personality extraction
        tone = "Professional & Engaging"
        if any(k in lower for k in ["funny", "humorous", "entertaining"]):
            tone = "Humorous & Fast-Paced"
        elif any(k in lower for k in ["urgent", "warning", "fomo", "serious"]):
            tone = "Direct & High-Stakes"
        elif any(k in lower for k in ["technical", "educational", "how-to", "framework"]):
            tone = "Authoritative & Actionable"

        # Target audience
        audience = "Small Business Owners & Founders"
        if any(k in lower for k in ["realtor", "real estate agent", "broker"]):
            audience = "Residential & Luxury Real Estate Agents"
        elif any(k in lower for k in ["agency", "media buyer", "marketer"]):
            audience = "Digital Marketing Agency Owners & Media Buyers"
        elif any(k in lower for k in ["consultant", "coach", "b2b"]):
            audience = "B2B Service Providers & Consultants"

        # Style mapping based on category and cues
        style = "stick-story"
        if "deep-dive" in lower or "3d" in lower or matched_cat in ["Meta Ads", "Digital Marketing"]:
            style = "deep-dive"
        elif "inside-out" in lower or "x-ray" in lower or matched_cat in ["Marketing Automation", "Branding"]:
            style = "inside-out"
        elif "tall-tale" in lower or "cartoon" in lower or matched_cat == "Business Growth":
            style = "tall-tale"
        elif "paper-atlas" in lower or "map" in lower or matched_cat == "Real Estate Marketing":
            style = "paper-atlas"

        # Clean topic title extraction
        topic_clean = prompt.strip()
        # Remove instructions like 'Create a 45-second Reel explaining...'
        topic_clean = re.sub(r"^(?:create|make|generate)\s+(?:an?\s+)?(?:\d+\s*-?\s*sec(?:ond)?\s+)?(?:reel|short|video)\s+(?:explaining|about|on)?\s*", "", topic_clean, flags=re.I).strip()
        if "." in topic_clean:
            topic_clean = topic_clean.split(".")[0].strip()

        return {
            "topic": topic_clean if topic_clean else prompt[:60],
            "target_category": matched_cat,
            "target_audience": audience,
            "tone": tone,
            "duration": max(20, min(90, duration)),
            "style": style,
        }

    # =========================================================================
    # 2. Creative Decisions
    # =========================================================================

    def make_creative_decisions(
        self,
        topic: str,
        category: str,
        target_audience: str,
        tone: str = "Authoritative & Actionable",
        requested_duration: int = 35,
        requested_style: Optional[str] = None,
        requested_voice: Optional[str] = None,
        requested_music: Optional[str] = None,
        requested_cta: Optional[str] = None
    ) -> CreativeDecision:
        """Determines full creative parameter package with sensible defaults."""
        style = requested_style if (requested_style and requested_style in VALID_STYLES) else "stick-story"
        voice = requested_voice if (requested_voice and requested_voice in VALID_VOICES) else "am_michael"
        music = requested_music if (requested_music and requested_music in VALID_MUSIC) else "bed"

        # Get niche-specific recommendations from HookFormatIntelligenceEngine
        niche_rec = self.hook_engine.get_niche_recommendations(category)

        hook_category = niche_rec.recommended_hook_categories[0] if niche_rec.recommended_hook_categories else "Contrarian / Myth-Busting"
        structure = niche_rec.recommended_structure
        cta = requested_cta or niche_rec.recommended_cta_strategy

        # Speaking pace (average words per second = 2.5)
        speaking_pace = 2.5

        # Visual treatment & transitions by style
        treatment_map = {
            "stick-story": ("Minimalist line art with dynamic eye animations and gold action cards", "Snap cut with kinetic impact"),
            "deep-dive": ("3D volumetric data pipeline with sunlit materials and shallow depth of field", "Smooth algorithmic camera push"),
            "inside-out": ("Flat 2D x-ray cutaways revealing hidden mechanics", "Lateral slide with graphic wipe"),
            "tall-tale": ("Stylized 2D cartoon characters operating in a sunny 3D world", "Pivoting camera orbit"),
            "paper-atlas": ("Handcrafted parchment maps with crimson routing ribbons", "Parchment fold transition"),
            "night-file": ("High-contrast single-source lighting with typewriter timestamps", "Shadow dissolve"),
        }
        visual_treatment, transition = treatment_map.get(style, ("Modern kinetic motion graphics", "Cut"))

        return CreativeDecision(
            topic=topic,
            target_category=category,
            target_audience=target_audience,
            tone=tone,
            target_duration=requested_duration,
            estimated_duration=float(requested_duration),
            hook_category=hook_category,
            script_structure=structure,
            video_style=style,
            voice=voice,
            speaking_pace=speaking_pace,
            music=music,
            visual_treatment=visual_treatment,
            scene_transition=transition,
            caption_style="Bold capitalized two-line kinetic cards with gold keyword accents",
            call_to_action=cta,
        )

    # =========================================================================
    # 3. Script Generation & Speaking Pace Calibration
    # =========================================================================

    def generate_script(
        self,
        decision: CreativeDecision
    ) -> Tuple[List[Dict[str, str]], float]:
        """Composes a high-converting script calibrated to the target duration.
        
        Returns:
            (script_lines, estimated_seconds)
            where each line has:
              - 'text': Narration spoken by local Kokoro TTS.
              - 'caps': 1-3 word bold sync captions with gold accents (e.g. 'STOP *BOOSTING | START *CONVERTING').
        """
        topic = decision.topic
        dur = decision.target_duration
        pace = decision.speaking_pace  # ~2.5 words/sec

        # Target word count: duration * pace (minus 15% margin for outro, pauses, and intro lead)
        target_words = int(dur * pace * 0.85)

        # 1. Opening Hook Line
        hook_templates = [
            f"Ever wonder why {topic.lower()} leaves most business owners completely stuck?",
            f"Here is the brutal truth about {topic.lower()} that nobody is telling you.",
            f"If you are still struggling with {topic.lower()}, you are making this one mistake.",
        ]
        hook_text = hook_templates[0]
        hook_caps = f"THE *TRUTH | ABOUT *{topic.upper()[:16]}"

        # 2. Problem Statement
        problem_text = "Most founders waste weeks chasing vanity attention instead of building qualified buyer flow."
        problem_caps = "CHASING *VANITY | LOSING *BUYERS"

        # 3. Explanation
        explanation_text = "When your messaging speaks to everyone, it resonates with nobody and converts zero paying clients."
        explanation_caps = "SPEAKING TO *EVERYONE | CONVERTING *NOBODY"

        # 4. Actionable Steps / Demonstration
        step1_text = "Step one: cut out generic fluff and focus solely on the single highest-stakes problem your client faces."
        step1_caps = "STEP *ONE: | TARGET *HIGH STAKES"

        step2_text = "Step two: show verifiable workflow evidence instead of making empty promises."
        step2_caps = "STEP *TWO: | PROVE *RESULTS"

        step3_text = "Step three: direct every viewer into a single automated, frictionless next step."
        step3_caps = "STEP *THREE: | SINGLE *ACTION"

        # 5. Payoff
        payoff_text = "Attention without conversion is just unpaid entertainment. Build systems that turn views into customers."
        payoff_caps = "VIEWS DON'T PAY *PAYROLL | SYSTEMS *DO"

        # 6. CTA Line
        cta_text = f"{decision.call_to_action}"
        cta_caps = "TAKE ACTION | LINK IN *BIO"

        # Assemble lines based on target duration
        if dur <= 30:
            lines = [
                {"text": hook_text, "caps": hook_caps},
                {"text": problem_text, "caps": problem_caps},
                {"text": step1_text, "caps": step1_caps},
                {"text": payoff_text, "caps": payoff_caps},
                {"text": cta_text, "caps": cta_caps},
            ]
        elif dur <= 45:
            lines = [
                {"text": hook_text, "caps": hook_caps},
                {"text": problem_text, "caps": problem_caps},
                {"text": explanation_text, "caps": explanation_caps},
                {"text": step1_text, "caps": step1_caps},
                {"text": step2_text, "caps": step2_caps},
                {"text": payoff_text, "caps": payoff_caps},
                {"text": cta_text, "caps": cta_caps},
            ]
        else:  # 60s+
            lines = [
                {"text": hook_text, "caps": hook_caps},
                {"text": problem_text, "caps": problem_caps},
                {"text": explanation_text, "caps": explanation_caps},
                {"text": step1_text, "caps": step1_caps},
                {"text": step2_text, "caps": step2_caps},
                {"text": step3_text, "caps": step3_caps},
                {"text": payoff_text, "caps": payoff_caps},
                {"text": cta_text, "caps": cta_caps},
            ]

        # Calculate actual word count and duration estimate
        total_words = sum(len(line["text"].split()) for line in lines)
        # Duration: (words / pace) + line pause gaps (0.26s each) + intro lead (0.35s) + outro (1.0s)
        estimated_duration = round((total_words / pace) + (len(lines) * 0.26) + 1.35, 1)

        return lines, estimated_duration

    # =========================================================================
    # 4. Scene Planning
    # =========================================================================

    def plan_scenes(
        self,
        decision: CreativeDecision,
        script_lines: List[Dict[str, str]]
    ) -> List[ScenePlan]:
        """Maps each script line into an individual visual production scene."""
        scenes: List[ScenePlan] = []
        pace = decision.speaking_pace

        visual_guidelines = [
            ("Hero character staring at a stagnant analytics dashboard with red drop-off arrows", "Camera slow dolly forward"),
            ("Split screen comparing empty inbox vs high view counts", "Hard cut to split contrast"),
            ("Abstract 3D funnel showing casual scrollers leaking out before checkout", "Lateral camera tracking shot"),
            ("High-contrast step card highlight with gold numeral and blueprint background", "Snap zoom on step badge"),
            ("Live workflow diagram showing lead routing straight to calendar booking", "Smooth pan across pipeline nodes"),
            ("Verification proof card showing verified revenue benchmarks", "Subtle pulse animation"),
            ("Hero founder working confidently at desk with automated green notifications", "Wide camera reveal"),
            ("Direct CTA closing screen with animated arrow pointing to comment/bio action", "Focus lock on CTA card"),
        ]

        for i, line in enumerate(script_lines):
            words = len(line["text"].split())
            line_duration = round((words / pace) + 0.35, 1)

            vis_desc, vis_dir = visual_guidelines[i % len(visual_guidelines)]

            scenes.append(ScenePlan(
                scene_number=i + 1,
                narration_text=line["text"],
                on_screen_caps=line["caps"],
                visual_description=vis_desc,
                visual_direction=vis_dir,
                transition=decision.scene_transition,
                estimated_duration=line_duration,
            ))

        return scenes

    # =========================================================================
    # 5. Faceless Shorts Project Rendering Packaging
    # =========================================================================

    def assemble_rendering_config(
        self,
        decision: CreativeDecision,
        script_lines: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Constructs the exact `script.json` configuration contract required by Faceless Shorts."""
        return {
            "title": decision.topic.title(),
            "style": decision.video_style,
            "voice": decision.voice,
            "speed": 1.0,
            "lead": 0.35,
            "outro": 1.0,
            "gap": 0.26,
            "music": decision.music,
            "sources": [
                "AdSync Marketing Intelligence & Performance Benchmarks",
                f"AdSync Creative Director — {decision.target_category}"
            ],
            "lines": script_lines,
        }

    def save_project_brief(
        self,
        brief: CreativeBrief,
        slug: Optional[str] = None
    ) -> Path:
        """Saves project configuration and script.json into a dedicated project directory."""
        clean_slug = slug or (
            "".join(c if c.isalnum() else "-" for c in brief.topic.lower()).strip("-")[:24]
            + f"-{uuid.uuid4().hex[:6]}"
        )
        proj_dir = self.output_dir / clean_slug
        proj_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write official script.json for Faceless Shorts rendering
        script_file = proj_dir / "script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(brief.rendering_config, f, indent=2)

        # 2. Write creative_brief.json with complete metadata
        brief.project_directory = str(proj_dir)
        brief_file = proj_dir / "creative_brief.json"
        with open(brief_file, "w", encoding="utf-8") as f:
            json.dump(brief.to_dict(), f, indent=2)

        return proj_dir

    # =========================================================================
    # 6. Mode A & Mode B Unified Generation Entrypoints
    # =========================================================================

    def create_brief_from_user_prompt(
        self,
        prompt: str,
        style: Optional[str] = None,
        voice: Optional[str] = None,
        music: Optional[str] = None,
        duration: Optional[int] = None,
        save_project: bool = True
    ) -> CreativeBrief:
        """MODE B: Natural-language brief comprehension and project assembly."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        parsed = self.parse_user_prompt(prompt)

        final_duration = duration or parsed["duration"]
        final_style = style or parsed["style"]

        decision = self.make_creative_decisions(
            topic=parsed["topic"],
            category=parsed["target_category"],
            target_audience=parsed["target_audience"],
            tone=parsed["tone"],
            requested_duration=final_duration,
            requested_style=final_style,
            requested_voice=voice,
            requested_music=music,
        )

        script_lines, est_duration = self.generate_script(decision)
        decision.estimated_duration = est_duration

        scene_plans = self.plan_scenes(decision, script_lines)
        rendering_config = self.assemble_rendering_config(decision, script_lines)

        brief = CreativeBrief(
            brief_id=f"brief_{uuid.uuid4().hex[:8]}",
            creation_mode="mode_b_user_topic",
            created_at=datetime.now(timezone.utc).isoformat(),
            topic=decision.topic,
            decisions=decision,
            script_lines=script_lines,
            scene_plans=scene_plans,
            rendering_config=rendering_config,
        )

        if save_project:
            self.save_project_brief(brief)

        return brief

    def create_brief_from_intelligence(
        self,
        category: str = "Meta Ads",
        trending_report: Optional[TrendingAnalysisReport] = None,
        duration: int = 35,
        save_project: bool = True
    ) -> CreativeBrief:
        """MODE A: Autonomous intelligence-driven content generation from trending data."""
        valid_cat = category if category in CATEGORY_TAXONOMY else "Meta Ads"

        # Extract trending topic if available
        topic = f"Why 'Boost Post' Destroys Conversion Tracking vs Full Funnel {valid_cat}"
        if trending_report and trending_report.emerging_topics:
            matching_topics = [t for t in trending_report.emerging_topics if t.category == valid_cat]
            if matching_topics:
                topic = f"The Truth About #{matching_topics[0].topic_key.title()} in 2026"

        decision = self.make_creative_decisions(
            topic=topic,
            category=valid_cat,
            target_audience="Founders, Agency Owners & Growth Marketers",
            tone="Authoritative & Actionable",
            requested_duration=duration,
        )

        script_lines, est_duration = self.generate_script(decision)
        decision.estimated_duration = est_duration

        scene_plans = self.plan_scenes(decision, script_lines)
        rendering_config = self.assemble_rendering_config(decision, script_lines)

        brief = CreativeBrief(
            brief_id=f"brief_{uuid.uuid4().hex[:8]}",
            creation_mode="mode_a_intelligence",
            created_at=datetime.now(timezone.utc).isoformat(),
            topic=decision.topic,
            decisions=decision,
            script_lines=script_lines,
            scene_plans=scene_plans,
            rendering_config=rendering_config,
        )

        if save_project:
            self.save_project_brief(brief)

        return brief
