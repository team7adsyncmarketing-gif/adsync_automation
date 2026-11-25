"""Unit tests for Stage 10 Cloud Preparation, Render Deployment, and Supabase Integrations."""
import unittest
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestStage10Cloud(unittest.TestCase):

    def test_cloud_preparation_files(self):
        # 10.1: requirements.txt and .env.example
        req_file = PROJECT_ROOT / "requirements.txt"
        self.assertTrue(req_file.exists(), "requirements.txt must exist")
        req_text = req_file.read_text(encoding="utf-8")
        self.assertIn("fastapi", req_text)
        self.assertIn("uvicorn", req_text)

        env_example = PROJECT_ROOT / ".env.example"
        self.assertTrue(env_example.exists(), ".env.example must exist")
        env_text = env_example.read_text(encoding="utf-8")
        self.assertIn("SUPABASE_URL", env_text)
        self.assertIn("RENDER_WORKER_URL", env_text)

    def test_render_blueprint_and_dockerfiles(self):
        # 10.2: render.yaml and Dockerfiles
        render_yaml = PROJECT_ROOT / "render.yaml"
        self.assertTrue(render_yaml.exists(), "render.yaml must exist")
        render_text = render_yaml.read_text(encoding="utf-8")
        self.assertIn("adsync-control-center", render_text)
        self.assertIn("adsync-render-worker", render_text)

        backend_docker = PROJECT_ROOT / "Dockerfile"
        self.assertTrue(backend_docker.exists(), "Root Dockerfile must exist")

        worker_docker = PROJECT_ROOT / "worker" / "Dockerfile"
        self.assertTrue(worker_docker.exists(), "Worker Dockerfile must exist")
        worker_docker_text = worker_docker.read_text(encoding="utf-8")
        self.assertIn("chromium", worker_docker_text)
        self.assertIn("ffmpeg", worker_docker_text)

    def test_supabase_schema_and_migration(self):
        # 10.3: Supabase SQL schema and migration script
        schema_file = PROJECT_ROOT / "scripts" / "supabase_schema.sql"
        self.assertTrue(schema_file.exists(), "supabase_schema.sql must exist")
        schema_text = schema_file.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.reels", schema_text)
        self.assertIn("CREATE TABLE IF NOT EXISTS public.video_catalog", schema_text)
        self.assertIn("CREATE TABLE IF NOT EXISTS public.render_jobs", schema_text)

        migrate_file = PROJECT_ROOT / "scripts" / "migrate_to_supabase.py"
        self.assertTrue(migrate_file.exists(), "migrate_to_supabase.py must exist")

    def test_worker_and_server_health_endpoints(self):
        # 10.4: Check healthz endpoint in dashboard server and worker
        from dashboard.server import healthcheck as server_health
        res = server_health()
        self.assertEqual(res["status"], "healthy")
        self.assertIn("supabase_configured", res)

        from worker.render_worker import healthcheck as worker_health
        w_res = worker_health()
        self.assertEqual(w_res["status"], "healthy")
        self.assertEqual(w_res["worker"], "adsync-render-worker")

if __name__ == "__main__":
    unittest.main()
