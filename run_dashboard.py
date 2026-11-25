"""Startup script for AdSync Control Center."""
import uvicorn
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    import os
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")

    print("=" * 65)
    print(" 🚀 Launching AdSync Control Center Dashboard")
    print("=" * 65)
    print(f" Dashboard URL: http://{host}:{port}")
    print(f" Backend APIs:  http://{host}:{port}/docs")
    print(" SQLite DB:     trend_engine/data/trends.db")
    print(" Press Ctrl+C to stop the dashboard.")
    print("=" * 65)
    uvicorn.run("dashboard.server:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
