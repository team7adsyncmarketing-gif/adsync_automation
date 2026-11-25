"""Unit tests for Stage 9 Dashboard Integrations."""
import unittest
from pathlib import Path
from dashboard.server import (
    app,
    get_overview,
    get_trends,
    get_competitors,
    create_competitor,
    delete_competitor,
    get_competitor_comparison,
    get_content_insights,
    generate_idea_api,
    CreateCompetitorRequest,
    GenerateIdeaRequest,
    STATIC_DIR,
)

class TestStage9Integrations(unittest.TestCase):

    def test_overview_includes_competitors(self):
        ov = get_overview()
        self.assertIn("total_competitors", ov)
        self.assertGreaterEqual(ov["total_competitors"], 1)
        self.assertIn("total_reels_analyzed", ov)
        self.assertGreaterEqual(ov["total_reels_analyzed"], 1)

    def test_trends_returns_reels_and_topics(self):
        trends = get_trends()
        self.assertIn("trending_reels", trends)
        self.assertIn("emerging_topics", trends)
        self.assertIn("niche_trends", trends)
        self.assertGreaterEqual(len(trends["trending_reels"]), 1)
        self.assertGreaterEqual(len(trends["emerging_topics"]), 1)
        
        # Verify reel fields
        r0 = trends["trending_reels"][0]
        self.assertIn("author_username", r0)
        self.assertIn("views", r0)
        self.assertIn("engagement_score", r0)
        self.assertIn("trending_score", r0)

    def test_competitor_management_and_comparison(self):
        # 1. List
        comps = get_competitors()
        self.assertIsInstance(comps, list)
        self.assertGreaterEqual(len(comps), 1)

        # 2. Create
        test_handle = "brand_scale_lab"
        res = create_competitor(CreateCompetitorRequest(
            handle=test_handle,
            category="Lead Generation Experts",
            notes="Automated B2B outreach test"
        ))
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["competitor"]["handle"], test_handle)

        # 3. Compare
        comp = get_competitor_comparison()
        self.assertIn("rankings_by_reach", comp)
        self.assertIn("rankings_by_engagement", comp)
        self.assertIn("rankings_by_popularity", comp)

        # 4. Delete
        del_res = delete_competitor(test_handle)
        self.assertEqual(del_res["status"], "deleted")
        self.assertEqual(del_res["handle"], test_handle)

    def test_content_insights_and_blueprints(self):
        insights = get_content_insights()
        self.assertIn("best_performing_hooks", insights)
        self.assertIn("niche_blueprints", insights)
        self.assertIn("Meta Ads", insights["niche_blueprints"])

        bp = insights["niche_blueprints"]["Meta Ads"]
        self.assertIn("recommended_hook_categories", bp)
        self.assertIn("recommended_structure", bp)
        self.assertIn("recommended_cta_strategy", bp)
        self.assertIn("sample_original_hook_templates", bp)
        self.assertGreaterEqual(len(bp["sample_original_hook_templates"]), 1)

    def test_generate_idea_saves_to_db(self):
        res = generate_idea_api(GenerateIdeaRequest(category="Meta Ads"))
        self.assertEqual(res["status"], "success")
        idea = res["idea"]
        self.assertTrue(idea["topic"])
        self.assertEqual(idea["target_category"], "Meta Ads")
        self.assertGreater(idea["opportunity_score"], 0)

    def test_static_ui_contains_stage9_tabs(self):
        html_path = STATIC_DIR / "index.html"
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")

        # Check tab buttons
        self.assertIn('data-tab="trends"', content)
        self.assertIn('data-tab="competitors"', content)
        self.assertIn('data-tab="insights"', content)

        # Check section IDs
        self.assertIn('id="tab-trends"', content)
        self.assertIn('id="tab-competitors"', content)
        self.assertIn('id="tab-insights"', content)

        # Check UI tables & cards
        self.assertIn('id="emerging-topics-table"', content)
        self.assertIn('id="discovered-reels-table"', content)
        self.assertIn('id="competitors-table"', content)
        self.assertIn('id="best-hooks-table"', content)
        self.assertIn('id="niche-blueprint-select"', content)

if __name__ == "__main__":
    unittest.main()
