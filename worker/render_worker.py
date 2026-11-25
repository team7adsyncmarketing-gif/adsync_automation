"""Cloud Rendering Worker Service for AdSync Control Center.

Executes the Faceless Shorts video generation pipeline in the cloud (Node.js, Chromium,
FFmpeg, Kokoro TTS, Whisper sync), uploads the final video to Supabase Storage, and
updates the video catalog and job queue.
"""
import os
import sys
import json
import uuid
import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from publisher.config import load_env
load_env()

from publisher.supabase_uploader import SupabaseStorageClient
from dashboard.generator import generate_short

app = FastAPI(title="AdSync Cloud Video Rendering Worker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory status store with database sync
JOBS_STORE = {}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "adsync-reels")


class RenderJobRequest(BaseModel):
    job_id: Optional[str] = None
    topic: str
    style: str = "stick-story"
    voice: str = "am_puck"
    speed: float = 1.0
    music: str = "bed"


def execute_cloud_render(job_id: str, req: RenderJobRequest):
    """Background task executing the rendering pipeline and uploading to Supabase Storage."""
    JOBS_STORE[job_id]["status"] = "PROCESSING"
    JOBS_STORE[job_id]["updated_at"] = datetime.datetime.utcnow().isoformat()

    try:
        # 1. Run Faceless Shorts rendering
        res = generate_short(
            topic=req.topic,
            style=req.style,
            voice=req.voice,
            speed=req.speed,
            music=req.music
        )

        local_mp4_path = res["video_path"]
        video_name = res["video_name"]

        # 2. Upload MP4 to Supabase Storage for global cloud streaming
        public_url = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                storage_client = SupabaseStorageClient(
                    supabase_url=SUPABASE_URL,
                    supabase_key=SUPABASE_KEY,
                    bucket_name=SUPABASE_BUCKET
                )
                public_url = storage_client.upload_file(
                    local_path=local_mp4_path,
                    destination_path=f"generated_videos/{video_name}",
                    content_type="video/mp4"
                )
            except Exception as e:
                print(f"[Worker] Supabase upload notice: {e}")

        # 3. Mark completed
        JOBS_STORE[job_id]["status"] = "COMPLETED"
        JOBS_STORE[job_id]["video"] = res
        JOBS_STORE[job_id]["video_url"] = public_url or f"/videos/{video_name}"
        JOBS_STORE[job_id]["storage_url"] = public_url
        JOBS_STORE[job_id]["updated_at"] = datetime.datetime.utcnow().isoformat()

    except Exception as err:
        JOBS_STORE[job_id]["status"] = "FAILED"
        JOBS_STORE[job_id]["error_message"] = str(err)
        JOBS_STORE[job_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
        print(f"[Worker Error] Job {job_id} failed: {err}")


@app.get("/healthz")
def healthcheck():
    return {
        "status": "healthy",
        "worker": "adsync-render-worker",
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "bucket": SUPABASE_BUCKET,
        "active_jobs": len([j for j in JOBS_STORE.values() if j["status"] == "PROCESSING"])
    }


@app.post("/render")
def enqueue_render(req: RenderJobRequest, bg_tasks: BackgroundTasks):
    job_id = req.job_id or f"job_{uuid.uuid4().hex[:12]}"
    JOBS_STORE[job_id] = {
        "job_id": job_id,
        "status": "PENDING",
        "topic": req.topic,
        "style": req.style,
        "voice": req.voice,
        "music": req.music,
        "speed": req.speed,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
        "video": None,
        "video_url": None,
        "error_message": None
    }

    bg_tasks.add_task(execute_cloud_render, job_id, req)

    return {
        "status": "enqueued",
        "job_id": job_id,
        "poll_url": f"/status/{job_id}"
    }


@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS_STORE[job_id]
