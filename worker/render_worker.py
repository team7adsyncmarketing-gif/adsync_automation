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

# Persistent status store (Disk + Supabase sync)
JOBS_FILE = PROJECT_ROOT / "output" / "jobs.json"

def load_jobs() -> dict:
    if JOBS_FILE.is_file():
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

JOBS_STORE = load_jobs()

def sync_job_to_supabase(job_id: str, job_data: dict):
    if not (SUPABASE_URL and SUPABASE_KEY):
        return
    try:
        import urllib.request
        endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/render_jobs"
        payload = {
            "job_id": job_id,
            "status": job_data.get("status", "PENDING"),
            "topic": job_data.get("topic", ""),
            "style": job_data.get("style", "stick-story"),
            "voice": job_data.get("voice", "am_puck"),
            "music": job_data.get("music", "bed"),
            "speed": float(job_data.get("speed", 1.0)),
            "video_url": job_data.get("video_url") or job_data.get("storage_url"),
            "error_message": job_data.get("error_message")
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"[Worker] Supabase job sync notice: {e}")

def fetch_job_from_supabase(job_id: str) -> Optional[dict]:
    if not (SUPABASE_URL and SUPABASE_KEY):
        return None
    try:
        import urllib.request
        endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/render_jobs?job_id=eq.{job_id}&select=*"
        req = urllib.request.Request(
            endpoint,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
            if rows:
                return rows[0]
    except Exception as e:
        print(f"[Worker] Supabase job fetch notice: {e}")
    return None

def save_job(job_id: str, job_data: dict):
    JOBS_STORE[job_id] = job_data
    # 1. Local disk
    try:
        JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        jobs = load_jobs()
        jobs[job_id] = job_data
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
    except Exception:
        pass
    # 2. Supabase Cloud Sync
    sync_job_to_supabase(job_id, job_data)

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
    save_job(job_id, JOBS_STORE[job_id])

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
        save_job(job_id, JOBS_STORE[job_id])

    except Exception as err:
        JOBS_STORE[job_id]["status"] = "FAILED"
        JOBS_STORE[job_id]["error_message"] = str(err)
        JOBS_STORE[job_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
        save_job(job_id, JOBS_STORE[job_id])
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
    job_record = {
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
    save_job(job_id, job_record)

    bg_tasks.add_task(execute_cloud_render, job_id, req)

    return {
        "status": "enqueued",
        "job_id": job_id,
        "poll_url": f"/status/{job_id}"
    }


@app.get("/jobs")
def list_jobs():
    """List all registered render jobs and states."""
    return list(load_jobs().values())


@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS_STORE:
        disk = load_jobs()
        if job_id in disk:
            JOBS_STORE[job_id] = disk[job_id]
        else:
            sb_job = fetch_job_from_supabase(job_id)
            if sb_job:
                JOBS_STORE[job_id] = sb_job
            else:
                raise HTTPException(status_code=404, detail="Job not found")
    return JOBS_STORE[job_id]


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, bg_tasks: BackgroundTasks):
    """Retries a failed job (Stage 10.5)."""
    if job_id not in JOBS_STORE:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS_STORE[job_id]
    job["status"] = "PENDING"
    job["error_message"] = None
    job["updated_at"] = datetime.datetime.utcnow().isoformat()
    req = RenderJobRequest(
        job_id=job_id,
        topic=job["topic"],
        style=job.get("style", "stick-story"),
        voice=job.get("voice", "am_puck"),
        speed=job.get("speed", 1.0),
        music=job.get("music", "bed")
    )
    bg_tasks.add_task(execute_cloud_render, job_id, req)
    return {"status": "retrying", "job_id": job_id}
