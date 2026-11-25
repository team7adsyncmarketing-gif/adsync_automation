"""AdSync Pipeline Bridge: Trend Engine -> Faceless Shorts Skill Integration.

Connects Trend Engine ideas or manual topic inputs into Faceless Shorts video production.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class ProductionConcept:
    topic: str
    target_category: str
    target_audience: str
    business_problem: str
    content_format: str
    faceless_short_style: str
    hooks: List[str]
    call_to_action: str
    source_type: str = "manual"  # 'database' or 'manual'
    source_id: Optional[str] = None


class PipelineBridge:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def load_concept_from_db(self, idea_id: str) -> Optional[ProductionConcept]:
        """Load an approved concept from SQLite trends database."""
        if not self.db_path:
            return None
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT idea_id, target_category, topic, hooks_json,
                   target_audience, business_problem, content_format,
                   faceless_short_style, call_to_action
            FROM adsync_ideas
            WHERE idea_id = ?
        """, (idea_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        import json
        hooks = json.loads(row[3]) if row[3] else []
        return ProductionConcept(
            source_id=row[0],
            source_type="database",
            target_category=row[1],
            topic=row[2],
            hooks=hooks,
            target_audience=row[4],
            business_problem=row[5],
            content_format=row[6],
            faceless_short_style=row[7],
            call_to_action=row[8]
        )

    def create_concept_from_topic(
        self,
        topic: str,
        style: str = "stick-story",
        target_audience: str = "Business Owners & Founders",
        category: str = "Instagram Marketing",
        cta: str = "DM us for the conversion blueprint."
    ) -> ProductionConcept:
        """Create a production concept from a manually entered topic."""
        return ProductionConcept(
            topic=topic,
            target_category=category,
            target_audience=target_audience,
            business_problem="Converting top-of-funnel discovery attention into qualified inbound buyers.",
            content_format="Step-by-step problem solver",
            faceless_short_style=style,
            hooks=[topic],
            call_to_action=cta,
            source_type="manual"
        )

