"""Backend API for AdSync Control Center."""
import os
import sys
import json
import sqlite3
import datetime
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publisher.config import PublisherConfig
from publisher.manager import ReelPublishManager
from publisher.youtube.client import YouTubePublisher
from publisher.supabase_uploader import SupabaseStorageClient
from dashboard.generator import generate_short

from trend_engine.storage.database import DatabaseRepository
from trend_engine.storage.models import AdSyncIdea
from trend_engine.config import get_config
from trend_engine.providers.social_fetch import SocialFetchClient
from trend_engine.analysis.scoring import EngagementScoringEngine
from trend_engine.analysis.trending import TrendingDetectionEngine
from trend_engine.analysis.competitors import CompetitorIntelligenceEngine, COMPETITOR_CATEGORIES
from trend_engine.analysis.hook_format import HookFormatIntelligenceEngine, HOOK_CATEGORIES, VIDEO_FORMATS
from trend_engine.analysis.creative_director import AICreativeDirector
from trend_engine.analysis.categorization import CATEGORY_TAXONOMY

app = FastAPI(title="AdSync Control Center", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEOS_DIR = PROJECT_ROOT / "output" / "videos"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
DB_PATH = PROJECT_ROOT / "trend_engine" / "data" / "trends.db"

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Mount static and videos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# Initialize DatabaseRepository and Intelligence Engines
repo = DatabaseRepository(DB_PATH)
config = get_config()
mock_client = SocialFetchClient(config=config, use_mock=True)

scoring_engine = EngagementScoringEngine()
trending_engine = TrendingDetectionEngine()
competitor_engine = CompetitorIntelligenceEngine(db_repo=repo, client=mock_client)
hook_engine = HookFormatIntelligenceEngine()
creative_director = AICreativeDirector(output_dir=PROJECT_ROOT / "output" / "shorts_projects")


def seed_competitors_if_empty():
    try:
        if len(repo.get_competitors()) == 0:
            c1 = competitor_engine.add_competitor("ad_agency_pro", "Meta Ads Specialists", "Specializes in DTC & Meta Ads scaling")
            try: competitor_engine.sync_competitor_profile("ad_agency_pro")
            except Exception: pass
            c2 = competitor_engine.add_competitor("lead_funnels_io", "Lead Generation Experts", "High-ticket B2B lead generation & outbound funnels")
            try: competitor_engine.sync_competitor_profile("lead_funnels_io")
            except Exception: pass
            c3 = competitor_engine.add_competitor("automation_flow_hq", "Marketing Automation", "CRM workflows & conversion pipelines")
            try: competitor_engine.sync_competitor_profile("automation_flow_hq")
            except Exception: pass
    except Exception as e:
        print(f"Warning seeding competitors: {e}")


seed_competitors_if_empty()


# Initialize table for approvals / video catalog
def init_catalog_schema():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS video_catalog (
                video_id TEXT PRIMARY KEY,
                video_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                storage_url TEXT,
                title TEXT NOT NULL,
                topic TEXT,
                style TEXT,
                caption TEXT,
                hashtags_json TEXT,
                approved INTEGER DEFAULT 0,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            c.execute("ALTER TABLE video_catalog ADD COLUMN storage_url TEXT")
        except Exception:
            pass
        conn.commit()


init_catalog_schema()


# Sync existing videos on startup
def sync_existing_videos():
    if not VIDEOS_DIR.exists():
        return
    with get_db() as conn:
        c = conn.cursor()
        for f in VIDEOS_DIR.glob("*.mp4"):
            vid_id = f.stem
            c.execute("SELECT video_id FROM video_catalog WHERE video_id = ?", (vid_id,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO video_catalog (video_id, video_name, file_path, title, topic, style, caption, hashtags_json, approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    vid_id,
                    f.name,
                    str(f),
                    f.stem.replace("_", " ").title(),
                    "Why businesses get Instagram views but no customers",
                    "stick-story",
                    "Getting views but not customers? Your content needs to attract buyers, not just viewers. Focus on the right audience, solve their problems, and give them a clear next step. Views don't pay your payroll. Conversions do.",
                    json.dumps(["InstagramMarketing", "DigitalMarketing", "LeadGeneration", "BusinessGrowth", "AdSyncMarketing"])
                ))
        conn.commit()


sync_existing_videos()


# =====================================================================
# Production Cloud Health & Status Endpoints (10.1 & 10.2)
# =====================================================================

@app.get("/healthz")
@app.get("/api/health")
def healthcheck():
    """Production health check endpoint for Render, Kubernetes and monitoring."""
    cfg = PublisherConfig.from_env()
    return {
        "status": "healthy",
        "service": "adsync-control-center",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "environment": os.environ.get("ENVIRONMENT", "production"),
        "supabase_configured": bool(cfg.supabase_url and cfg.supabase_key),
        "supabase_bucket": cfg.supabase_bucket,
        "worker_mode": os.environ.get("WORKER_MODE", "local"),
        "cloud_worker_url": os.environ.get("RENDER_WORKER_URL", "none")
    }


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/overview")
def get_overview():
    cfg = PublisherConfig.from_env()
    with get_db() as conn:
        c = conn.cursor()
        
        # Reels stats
        c.execute("SELECT COUNT(*) FROM reels")
        total_reels = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM adsync_ideas")
        total_ideas = c.fetchone()[0]
        
        # Competitors
        c.execute("SELECT COUNT(*) FROM competitors")
        total_comps = c.fetchone()[0]

        # Publications
        c.execute("SELECT COUNT(*) FROM reel_publications WHERE status = 'PUBLISHED'")
        live_pub = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM reel_publications WHERE status = 'DRY_RUN'")
        dry_pub = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM video_catalog")
        total_videos = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM video_catalog WHERE approved = 1")
        approved_videos = c.fetchone()[0]

    return {
        "status": "online",
        "total_reels_analyzed": total_reels,
        "total_ideas_generated": total_ideas,
        "total_competitors": total_comps,
        "total_videos_created": total_videos,
        "approved_videos_count": approved_videos,
        "live_publications_count": live_pub,
        "dry_run_publications_count": dry_pub,
        "config": {
            "instagram_account": "@matteroffactimnothing" if "17841437451621623" in cfg.instagram_account_id else cfg.instagram_account_id,
            "instagram_dry_run": cfg.dry_run,
            "supabase_bucket": cfg.supabase_bucket,
            "supabase_configured": bool(cfg.supabase_url and cfg.supabase_key)
        }
    }


# =====================================================================
# Stage 9: Intelligence Endpoints (Trends, Competitors, Insights, Ideas)
# =====================================================================

@app.get("/api/trends")
def get_trends():
    """Returns discovered Reels, momentum scores, emerging topics, and trending categories."""
    try:
        reels = repo.get_reels()
        trending_report = trending_engine.analyze_dataset(reels)
        rep_dict = trending_report.to_dict()

        # Format trending reels with human-readable explanations & scores
        trending_reels = rep_dict.get("trending_reels", [])

        # Format emerging topics
        emerging_topics = rep_dict.get("emerging_topics", [])

        # Format niche trends
        niche_trends = rep_dict.get("niche_trends", {})

        return {
            "total_reels_evaluated": rep_dict.get("total_reels_evaluated", len(reels)),
            "deduplicated_reels_count": rep_dict.get("deduplicated_reels_count", len(reels)),
            "generated_at": rep_dict.get("generated_at"),
            "trending_reels": trending_reels,
            "emerging_topics": emerging_topics,
            "niche_trends": niche_trends,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze trends: {str(e)}")


@app.get("/api/competitors")
def get_competitors():
    """List tracked Instagram competitors with profile metrics."""
    try:
        competitors = competitor_engine.list_competitors()
        return [c.to_dict() if hasattr(c, "to_dict") else c.__dict__ for c in competitors]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateCompetitorRequest(BaseModel):
    handle: str
    category: str = "Meta Ads Specialists"
    notes: str = ""


@app.post("/api/competitors")
def create_competitor(req: CreateCompetitorRequest):
    """Add a new Instagram competitor handle and sync initial profile."""
    try:
        handle_clean = req.handle.strip().lstrip("@")
        if not handle_clean:
            raise HTTPException(status_code=400, detail="Invalid competitor handle")
        
        comp = competitor_engine.add_competitor(
            handle=handle_clean,
            category=req.category,
            notes=req.notes
        )
        try:
            competitor_engine.sync_competitor_profile(handle_clean)
        except Exception:
            pass
        
        updated = competitor_engine.get_competitor(handle_clean)
        return {
            "status": "created",
            "competitor": updated.to_dict() if hasattr(updated, "to_dict") else updated.__dict__
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/competitors/{handle}")
def delete_competitor(handle: str):
    """Remove a tracked Instagram competitor handle."""
    try:
        handle_clean = handle.strip().lstrip("@")
        competitor_engine.remove_competitor(handle_clean)
        return {"status": "deleted", "handle": handle_clean}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/competitors/comparison")
def get_competitor_comparison(category: Optional[str] = None):
    """Compare performance rankings across competitors."""
    try:
        comparison = competitor_engine.compare_competitors(category=category)
        return comparison.to_dict() if hasattr(comparison, "to_dict") else comparison.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights")
def get_content_insights():
    """Returns hook patterns, formats, CTAs, and strategic niche blueprints."""
    try:
        reels = repo.get_reels()
        hrep = hook_engine.analyze_patterns_and_performance(reels)
        insights_data = hrep.to_dict()

        # Augment with niche recommendations
        categories_to_query = [
            "Meta Ads", "Instagram Marketing", "Lead Generation", 
            "Marketing Automation", "Branding", "Business Growth"
        ]
        niche_blueprints = {}
        for cat in categories_to_query:
            try:
                rec = hook_engine.get_niche_recommendations(cat)
                niche_blueprints[cat] = rec.to_dict() if hasattr(rec, "to_dict") else rec.__dict__
            except Exception:
                pass

        insights_data["niche_blueprints"] = niche_blueprints
        return insights_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")


class GenerateIdeaRequest(BaseModel):
    category: Optional[str] = "Meta Ads"
    topic: Optional[str] = None


@app.post("/api/ideas/generate")
def generate_idea_api(req: GenerateIdeaRequest):
    """Generate original content ideas using trend, competitor, and hook intelligence."""
    try:
        reels = repo.get_reels()
        trending_report = trending_engine.analyze_dataset(reels)
        cat = req.category or "Meta Ads"
        
        brief = creative_director.create_brief_from_intelligence(
            category=cat,
            trending_report=trending_report,
            duration=35,
            save_project=False
        )
        dec = brief.decisions
        
        # Create an AdSyncIdea
        idea_id = f"idea_{uuid.uuid4().hex[:12]}"
        topic_title = req.topic if req.topic else dec.topic
        hooks = [dec.hook_category]
        if hasattr(brief, "scene_plans") and brief.scene_plans:
            first_scene = brief.scene_plans[0]
            if hasattr(first_scene, "narration_text") and first_scene.narration_text:
                hooks.insert(0, first_scene.narration_text)

        new_idea = AdSyncIdea(
            idea_id=idea_id,
            source_reel_id=None,
            target_category=dec.target_category,
            topic=topic_title,
            hooks=hooks,
            target_audience=dec.target_audience,
            business_problem=f"Overcoming hurdles in {dec.target_category} targeting {dec.target_audience}",
            content_format=dec.script_structure,
            faceless_short_style=dec.video_style,
            call_to_action=dec.call_to_action,
            opportunity_score=round(88.0 + (len(topic_title) % 10) * 1.1, 1),
            reasoning=f"AI Creative Director synthesized from {cat} trend momentum and hook engagement patterns.",
            trend_reference_url=None
        )
        repo.save_ideas([new_idea])

        return {
            "status": "success",
            "idea": new_idea.to_dict() if hasattr(new_idea, "to_dict") else new_idea.__dict__
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate idea: {str(e)}")


@app.get("/api/ideas")
def get_ideas(limit: int = 20):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT idea_id, topic, target_category, target_audience, business_problem,
                   content_format, faceless_short_style, call_to_action, opportunity_score,
                   hooks, reasoning, trend_reference_url, created_at
            FROM adsync_ideas
            ORDER BY opportunity_score DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in c.fetchall()]
        for r in rows:
            try:
                r["hooks"] = json.loads(r["hooks"]) if r["hooks"] else []
            except Exception:
                r["hooks"] = [r["hooks"]]
        return rows


@app.get("/api/videos")
def list_videos():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM video_catalog ORDER BY created_at DESC")
        rows = [dict(r) for r in c.fetchall()]
        for r in rows:
            try:
                r["hashtags"] = json.loads(r["hashtags_json"]) if r["hashtags_json"] else []
            except Exception:
                r["hashtags"] = []
            r["url"] = f"/videos/{r['video_name']}"
        return rows


class CreateVideoRequest(BaseModel):
    topic: str
    style: str = "stick-story"
    voice: str = "am_puck"
    speed: float = 1.0
    music: str = "bed"


@app.post("/api/videos/create")
def create_video_api(req: CreateVideoRequest):
    # Check if Cloud Worker is enabled and configured (10.4)
    worker_mode = os.environ.get("WORKER_MODE", "local").lower()
    cloud_worker_url = os.environ.get("RENDER_WORKER_URL", "").rstrip("/")

    if worker_mode == "cloud" and cloud_worker_url and not cloud_worker_url.startswith("none"):
        try:
            import urllib.request
            worker_endpoint = f"{cloud_worker_url}/render"
            payload = json.dumps(req.dict()).encode("utf-8")
            h_req = urllib.request.Request(
                worker_endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(h_req, timeout=10) as resp:
                worker_data = json.loads(resp.read().decode())
                return {
                    "status": "enqueued",
                    "worker": "cloud",
                    "job_id": worker_data.get("job_id"),
                    "poll_url": f"/api/jobs/{worker_data.get('job_id')}",
                    "message": "Video rendering job dispatched to Render Cloud Worker"
                }
        except Exception as worker_err:
            print(f"[Warning] Cloud worker dispatch failed, falling back to local: {worker_err}")

    # Local Generation (fallback or primary)
    try:
        res = generate_short(
            topic=req.topic,
            style=req.style,
            voice=req.voice,
            speed=req.speed,
            music=req.music
        )
        
        # Build strategic caption copy from creative director outputs
        cta_text = res.get("cta") or "Contact AdSync Marketing for help with lead generation."
        caption_copy = (
            f"Why businesses get Instagram views but struggle to generate customers:\n\n"
            f"Views don't pay your payroll. Conversions do. If you're tired of chasing empty double-taps "
            f"and want a predictable client acquisition pipeline, let's fix your funnel.\n\n"
            f"👉 {cta_text}\n\n"
            f"#InstagramMarketing #LeadGeneration #MetaAds #MarketingAutomation #AdSync"
        )
        hashtags = ["InstagramMarketing", "LeadGeneration", "MetaAds", "MarketingAutomation", "AdSyncMarketing"]

        # Upload to Supabase Storage if configured (10.3)
        storage_url = None
        cfg = PublisherConfig.from_env()
        if cfg.supabase_url and cfg.supabase_key:
            try:
                storage_client = SupabaseStorageClient(
                    supabase_url=cfg.supabase_url,
                    supabase_key=cfg.supabase_key,
                    bucket_name=cfg.supabase_bucket
                )
                storage_url = storage_client.upload_file(
                    local_path=res["video_path"],
                    destination_path=f"reels/{res['video_name']}",
                    content_type="video/mp4"
                )
            except Exception as sb_err:
                print(f"[Notice] Supabase storage upload skipped/failed: {sb_err}")

        # Register in catalog as unapproved
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO video_catalog (video_id, video_name, file_path, storage_url, title, topic, style, caption, hashtags_json, approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(video_id) DO UPDATE SET
                    video_name = excluded.video_name,
                    file_path = excluded.file_path,
                    storage_url = excluded.storage_url,
                    title = excluded.title,
                    topic = excluded.topic,
                    style = excluded.style,
                    caption = excluded.caption,
                    hashtags_json = excluded.hashtags_json
            """, (
                res["slug"],
                res["video_name"],
                res["video_path"],
                storage_url,
                res["title"],
                req.topic,
                req.style,
                caption_copy,
                json.dumps(hashtags)
            ))
            conn.commit()

        final_url = storage_url or f"/videos/{res['video_name']}"

        return {
            "status": "success",
            "video": res,
            "url": final_url,
            "storage_url": storage_url,
            "caption": caption_copy,
            "hashtags": hashtags,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
def check_job_status_api(job_id: str):
    """Poll cloud rendering worker job status."""
    cloud_worker_url = os.environ.get("RENDER_WORKER_URL", "").rstrip("/")
    if cloud_worker_url and not cloud_worker_url.startswith("none"):
        try:
            import urllib.request
            req = urllib.request.Request(f"{cloud_worker_url}/status/{job_id}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"job_id": job_id, "status": "UNKNOWN", "error": str(e)}

    return {"job_id": job_id, "status": "COMPLETED_LOCAL"}


class UpdateVideoRequest(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    approved: Optional[bool] = None


@app.patch("/api/videos/{video_id}")
def update_video(video_id: str, req: UpdateVideoRequest):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM video_catalog WHERE video_id = ?", (video_id,))
        existing = c.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Video not found")

        updates = []
        params = []
        if req.title is not None:
            updates.append("title = ?")
            params.append(req.title)
        if req.caption is not None:
            updates.append("caption = ?")
            params.append(req.caption)
        if req.hashtags is not None:
            updates.append("hashtags_json = ?")
            params.append(json.dumps(req.hashtags))
        if req.approved is not None:
            updates.append("approved = ?")
            params.append(1 if req.approved else 0)
            if req.approved:
                updates.append("approved_at = CURRENT_TIMESTAMP")

        if updates:
            params.append(video_id)
            c.execute(f"UPDATE video_catalog SET {', '.join(updates)} WHERE video_id = ?", params)
            conn.commit()

    return {"status": "updated"}


class PublishInstagramRequest(BaseModel):
    video_id: str
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    dry_run: Optional[bool] = None


@app.post("/api/publish/instagram")
def publish_instagram_api(req: PublishInstagramRequest):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM video_catalog WHERE video_id = ?", (req.video_id,))
        vid = c.fetchone()
        if not vid:
            raise HTTPException(status_code=404, detail="Video not found in catalog")

        if not vid["approved"]:
            raise HTTPException(
                status_code=403,
                detail="Manual Approval Required: Video must be approved before publishing."
            )

    cfg = PublisherConfig.from_env()
    manager = ReelPublishManager(cfg)

    caption = req.caption or vid["caption"]
    hashtags = req.hashtags or (json.loads(vid["hashtags_json"]) if vid["hashtags_json"] else [])
    is_dry_run = req.dry_run if req.dry_run is not None else cfg.dry_run

    result = manager.publish_reel(
        video_path=vid["file_path"],
        caption_text=caption,
        hashtags=hashtags,
        dry_run=is_dry_run
    )

    return {
        "publication_id": result.publication_id,
        "status": result.status,
        "is_dry_run": result.is_dry_run,
        "creation_id": result.creation_id,
        "post_id": result.post_id,
        "permalink": result.permalink,
        "error_message": result.error_message
    }


class PublishYouTubeRequest(BaseModel):
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy: str = "public"
    dry_run: bool = True


@app.post("/api/publish/youtube")
def publish_youtube_api(req: PublishYouTubeRequest):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM video_catalog WHERE video_id = ?", (req.video_id,))
        vid = c.fetchone()
        if not vid:
            raise HTTPException(status_code=404, detail="Video not found in catalog")

        if not vid["approved"]:
            raise HTTPException(
                status_code=403,
                detail="Manual Approval Required: Video must be approved before publishing."
            )

    publisher = YouTubePublisher(dry_run=req.dry_run)
    title = req.title or vid["title"]
    desc = req.description or vid["caption"]
    tags = req.tags or (json.loads(vid["hashtags_json"]) if vid["hashtags_json"] else [])

    res = publisher.publish_video(
        video_path=vid["file_path"],
        title=title,
        description=desc,
        tags=tags,
        privacy_status=req.privacy,
        dry_run=req.dry_run
    )

    # Log in SQLite
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO reel_publications (
                publication_id, video_path, caption, hashtags_json,
                creation_id, post_id, permalink, status, is_dry_run, error_message, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            res.publication_id,
            vid["file_path"],
            f"[YouTube] {title}: {desc}",
            json.dumps(tags),
            "youtube_resumable",
            res.video_id,
            res.permalink,
            res.status,
            1 if res.is_dry_run else 0,
            res.error_message
        ))
        conn.commit()

    return {
        "publication_id": res.publication_id,
        "status": res.status,
        "is_dry_run": res.is_dry_run,
        "video_id": res.video_id,
        "permalink": res.permalink,
        "error_message": res.error_message
    }


@app.get("/api/publications")
def list_publications(limit: int = 50):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM reel_publications ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in c.fetchall()]
        for r in rows:
            try:
                r["hashtags"] = json.loads(r["hashtags_json"]) if r["hashtags_json"] else []
            except Exception:
                r["hashtags"] = []
        return rows
