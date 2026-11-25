"""Daily intelligence reporting module for AdSync Trend Engine."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..storage.models import ReelItem, ReelAnalysis, AdSyncIdea
from ..storage.database import DatabaseRepository


class DailyReportGenerator:
    """Generates ranked daily intelligence reports in Markdown format."""

    def __init__(self, db: DatabaseRepository, output_dir: Optional[Path] = None):
        self.db = db
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = db.db_path.parent.parent / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, is_mock: bool = True) -> str:
        """Compiles the daily trend intelligence report filtered strictly by is_mock status."""
        stats = self.db.get_summary_stats(is_mock=is_mock)
        ideas = self.db.get_top_ideas(is_mock=is_mock, limit=20)
        reels = self.db.get_reels(is_mock=is_mock, limit=20)

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = []
        lines.append(f"# AdSync Autonomous Social Media Engine — Daily Trend Intelligence")
        lines.append(f"**Date:** {date_str}  ")
        lines.append(f"**Generated:** {timestamp}  ")

        if is_mock:
            lines.append("> [!WARNING]")
            lines.append("> **DATA SOURCE NOTICE: MOCK DATA MODE**")
            lines.append("> This report was compiled using synthetic sample Instagram Reel data for offline pipeline verification.")
            lines.append("> These metrics and trends represent architectural test fixtures, not live Instagram production signals.")
        else:
            lines.append("> [!NOTE]")
            lines.append("> **DATA SOURCE NOTICE: LIVE INSTAGRAM SIGNALS**")
            lines.append("> Extracted via Social Fetch API (`GET /v2/instagram/reels/trending`).")

        lines.append("\n---\n")

        # 1. Executive Summary & Sample Telemetry
        telemetry = stats.get("telemetry", {})
        total_retrieved = stats.get("total_reels", len(reels))
        relevant_cnt = stats.get("relevant_reels", 0)
        irrelevant_cnt = stats.get("irrelevant_reels", 0)

        lines.append("## 1. Executive Trend Summary")
        lines.append(f"- **Total Reels Retrieved in Batch:** {total_retrieved}")
        lines.append(f"- **Data Ingestion Mode:** {'MOCK / TEST FIXTURE' if is_mock else 'LIVE SOCIAL FETCH PRODUCTION'}")
        lines.append(f"- **Marketing Relevant Reels:** {relevant_cnt} ({(relevant_cnt / max(total_retrieved, 1)) * 100:.1f}%)")
        lines.append(f"- **Irrelevant / Non-Marketing Reels:** {irrelevant_cnt} ({(irrelevant_cnt / max(total_retrieved, 1)) * 100:.1f}%)")
        lines.append(f"- **Top Marketing Verticals:** {', '.join([c for c in stats.get('categories', {}).keys() if c != 'Other / Irrelevant'][:4]) or 'None identified'}")
        lines.append(f"- **AdSync Concepts Generated:** {len(ideas)}")
        lines.append("\n")

        # Sample size and discovery batch constraint notices
        if not is_mock:
            lines.append("> [!IMPORTANT]")
            lines.append(f"> **SAMPLE SIZE & DISCOVERY BATCH AUDIT (N = {total_retrieved})**")
            lines.append("> 1. **Discovery Stream Disclaimer:** This endpoint (`/v2/instagram/reels/trending`) delivers an unranked public discovery batch. Presence in this feed does not signify verified viral ranking.")
            lines.append("> 2. **Statistical Significance Caveat:** A single batch of sample reels is insufficient to draw broad platform-wide algorithmic conclusions. Insights below represent direct observations from this specific sample only.")
            lines.append("\n")

        # 2. Data Completeness & Metric Availability Audit
        lines.append("## 2. Engagement Metrics & Metadata Completeness Audit")
        lines.append("| Metric / Telemetry Field | Available (Non-Null) | Missing / Null / Hidden | Audit Assessment |")
        lines.append("| :--- | :--- | :--- | :--- |")
        lines.append(f"| **Play / View Count** | {telemetry.get('with_plays', 0)} | {telemetry.get('null_plays', 0)} | {'Verified from Instagram' if telemetry.get('with_plays') else 'Null in discovery stream'} |")
        lines.append(f"| **Like Count** | {telemetry.get('with_likes', 0)} | {telemetry.get('null_likes', 0)} | {'Publicly visible' if telemetry.get('with_likes') else 'Likes hidden or null'} |")
        lines.append(f"| **Comment Count** | {telemetry.get('with_comments', 0)} | {telemetry.get('null_comments', 0)} | {'Comments tracked' if telemetry.get('with_comments') else 'Unrecorded'} |")
        lines.append(f"| **Share / Save Count** | {telemetry.get('with_shares', 0)} | {telemetry.get('null_shares', 0)} | {'Shares tracked' if telemetry.get('with_shares') else 'Unrecorded in public scrape'} |")
        lines.append(f"| **Audio Metadata** | {telemetry.get('with_audio', 0)} | {telemetry.get('missing_audio', 0)} | {'Audio tags extracted' if telemetry.get('with_audio') else 'No audio metadata'} |")
        lines.append(f"| **Caption Text** | {telemetry.get('with_caption', 0)} | {telemetry.get('missing_caption', 0)} | {'Captions extracted' if telemetry.get('with_caption') else 'Empty captions'} |")
        lines.append("\n")

        # 3. Content Formats Breakdown
        lines.append("## 3. Dominant Content Formats")
        lines.append("| Format | Count | Virality Archetype |")
        lines.append("| :--- | :--- | :--- |")
        format_archetypes = {
            "Screen Recording / Workflow Breakdown": "High saves, B2B utility, educational authority",
            "Direct Storytelling / Talking Head": "High watch-time retention, founder intimacy",
            "Text Overlay / Kinetic Typography": "Fast scan, high shareability, mobile native",
            "Cinematic B-Roll Walkthrough": "Aesthetic luxury appeal, visual proof",
            "Fast-Paced Explainer with On-Screen Graphics": "Mass engagement, high completion rate",
        }
        for fmt, cnt in stats.get("formats", {}).items():
            arch = format_archetypes.get(fmt, "Engaging visual pacing")
            lines.append(f"| **{fmt}** | {cnt} | {arch} |")
        lines.append("\n")

        # 3. Hook Pattern Taxonomy
        lines.append("## 3. Strongest Hook Patterns & Persuasion Triggers")
        lines.append("| Hook Type | Frequency | Why It Attracts Attention (Psychological Trigger) |")
        lines.append("| :--- | :--- | :--- |")
        hook_triggers = {
            "Contrarian / Myth-Busting": "Disrupts autopilot scrolling by attacking a common industry sacred cow.",
            "Curiosity Gap": "Creates an open cognitive loop that forces the viewer to stay until the reveal.",
            "Framework / Actionable Blueprint": "Reduces cognitive friction by promising an immediate, sequential step-by-step fix.",
            "Case Study / Proven Results": "Overcomes buyer skepticism through undeniable numerical proof and documentation.",
            "Diagnostic / Problem-Agitation": "Directly pinpoints an active operational pain point, pre-qualifying the target audience.",
            "Insight / Provocative Question": "Stimulates curiosity through an unexpected, high-stakes question.",
        }
        for hk, cnt in stats.get("hook_types", {}).items():
            trig = hook_triggers.get(hk, "Captures visual and intellectual focus.")
            lines.append(f"| **{hk}** | {cnt} | {trig} |")
        lines.append("\n")

        # 4. Top Marketing Categories
        lines.append("## 4. Category Performance & Share of Voice")
        lines.append("| Category | Ingested Reels | Strategic Relevance for AdSync |")
        lines.append("| :--- | :--- | :--- |")
        relevance_notes = {
            "Meta Ads": "Primary revenue driver; media buyers actively hunt for CPA-reduction tactics.",
            "Marketing Automation": "Direct product match; demonstrates AdSync's AI-agent and workflow capabilities.",
            "Instagram Marketing": "Platform-native relevance; creators and brands seek algorithm adaptation.",
            "Lead Generation": "Universal B2B pain point; high commercial value for booking sales appointments.",
            "Real Estate Marketing": "High-ticket niche; agents readily adopt cinematic territory-dominance videos.",
            "Branding": "Appeals to founders wanting pricing power and anti-commodity positioning.",
            "Business Growth": "Speaks to agency owners seeking operational leverage and productized services.",
            "Digital Marketing": "Broadest awareness layer; captures full-funnel digital strategy demand.",
            "Other / Irrelevant": "Non-marketing discovery content filtered out from AdSync video ideation.",
        }
        for cat, cnt in stats.get("categories", {}).items():
            note = relevance_notes.get(cat, "Discovery content.")
            lines.append(f"| **{cat}** | {cnt} | {note} |")
        lines.append("\n---\n")

        # 5. Top Marketing-Related Hooks
        lines.append("## 5. Top Marketing-Related Hooks (Extracted from Batch)")
        lines.append("> [!NOTE]")
        lines.append("> Hooks below are surfaced based on copywriting structure and topical marketing relevance.")
        lines.append("> Presence in this discovery batch does not indicate viral ranking.\n")

        with self.db._get_connection() as conn:
            hook_rows = conn.execute("""
                SELECT r.shortcode, r.author_username, a.primary_category, a.hook_text, a.hook_type, a.content_format
                FROM reel_analyses a
                JOIN reels r ON a.reel_id = r.reel_id
                WHERE a.primary_category != 'Other / Irrelevant' AND r.is_mock = ?
                ORDER BY a.confidence_score DESC
                LIMIT 10
            """, [1 if is_mock else 0]).fetchall()

        if hook_rows:
            lines.append("| Target Category | Creator | Opening Hook | Hook Type | Content Format |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for hr in hook_rows:
                lines.append(f"| **{hr['primary_category']}** | @{hr['author_username']} | *\"{hr['hook_text']}\"* | {hr['hook_type']} | {hr['content_format']} |")
        else:
            lines.append("*No marketing-relevant hooks identified in this discovery batch.*")
        lines.append("\n---\n")

        # 6. Top AdSync Reel Concepts
        lines.append("## 6. Top Ranked AdSync Marketing Reel Concepts")
        lines.append("Original, high-converting video concepts engineered for the Phase 1 Faceless Shorts engine:\n")

        for idx, idea in enumerate(ideas[:20], 1):
            lines.append(f"### #{idx}. {idea.topic}")
            lines.append(f"- **Target Vertical:** `{idea.target_category}` | **Opportunity Score:** `{idea.opportunity_score} / 100`")
            lines.append(f"- **Target Audience:** {idea.target_audience}")
            lines.append(f"- **Core Business Problem:** {idea.business_problem}")
            lines.append(f"- **Suggested Content Format:** {idea.content_format}")
            lines.append(f"- **Recommended Faceless Shorts Style:** `{idea.faceless_short_style}`")
            lines.append(f"- **Three Original Opening Hooks:**")
            for h_idx, hook in enumerate(idea.hooks, 1):
                lines.append(f"  {h_idx}. *\"{hook}\"*")
            lines.append(f"- **Call to Action (CTA):** {idea.call_to_action}")
            if idea.trend_reference_url:
                lines.append(f"- **Trend Inspiration Signal:** [{idea.trend_reference_url}]({idea.trend_reference_url})")
            lines.append(f"- **Strategic Rationale:** {idea.reasoning}")
            lines.append("\n")

        report_md = "\n".join(lines)

        # Write to file
        mode_suffix = "mock" if is_mock else "live"
        report_file = self.output_dir / f"daily_report_{mode_suffix}_{date_str}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)

        # Also write canonical daily_report_YYYY-MM-DD.md
        canonical_file = self.output_dir / f"daily_report_{date_str}.md"
        with open(canonical_file, "w", encoding="utf-8") as f:
            f.write(report_md)

        return report_md
