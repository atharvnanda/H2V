"""
app.py — FastAPI backend for H2V

Endpoints
─────────
  POST /upload          Upload a video file → returns { job_id }
  GET  /status/{job_id} Poll job state → { state, detail, output_url? }
  GET  /download/{job_id} Serve the finished output video

The existing classify → transform → FFmpeg pipeline runs untouched
inside a background thread.
"""
from __future__ import annotations

import importlib
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="H2V — Horizontal to Vertical", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = Path(__file__).parent / "uploads"
OUTPUT_DIR = Path(__file__).parent / "output"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── In-memory job store ───────────────────────────────────────────────────────
# { job_id: { "state": "processing"|"done"|"error", "detail": str, "output": Path|None } }
jobs: dict[str, dict] = {}


# ── Background pipeline worker ───────────────────────────────────────────────
def _run_pipeline(job_id: str, input_path: Path, output_path: Path) -> None:
    """Run the full classify → transform → FFmpeg pipeline in a thread."""
    try:
        # ── Step 1: Classify ──────────────────────────────────────────────
        print(f"\n[h2v] [{job_id}] Starting pipeline for: {input_path.name}")
        jobs[job_id]["detail"] = "Detecting template…"
        from core.classifier import classify

        template_name = classify(str(input_path))
        print(f"[h2v] [{job_id}] Detected template: {template_name}")
        jobs[job_id]["detail"] = f"Detected: {template_name}. Converting…"

        # ── Step 2: Load transformer & build FFmpeg command ───────────────
        module_path = f"templates.{template_name}.transformer"
        transformer = importlib.import_module(module_path)
        cmd = transformer.build_command(str(input_path), str(output_path))
        print(f"[h2v] [{job_id}] FFmpeg command built — running conversion…")

        # ── Step 3: Run FFmpeg ────────────────────────────────────────────
        jobs[job_id]["detail"] = "Finalising…"
        from core import ffmpeg_runner

        ffmpeg_runner.run(cmd)

        # ── Done ──────────────────────────────────────────────────────────
        jobs[job_id]["state"] = "done"
        jobs[job_id]["detail"] = "Conversion complete"
        jobs[job_id]["output"] = output_path
        print(f"[h2v] [{job_id}] ✓ Done → {output_path.name}")

    except Exception as exc:
        jobs[job_id]["state"] = "error"
        jobs[job_id]["detail"] = str(exc)
        print(f"[h2v] [{job_id}] ✗ Error: {exc}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Accept a video upload, start the pipeline, return a job_id."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    job_id = uuid.uuid4().hex[:12]

    # Save uploaded file
    ext = Path(file.filename).suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{job_id}{ext}"
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Prepare output path
    output_path = OUTPUT_DIR / f"{job_id}_vertical.mp4"

    # Register job
    jobs[job_id] = {
        "state": "processing",
        "detail": "Queued — starting pipeline…",
        "output": None,
    }

    # Launch background thread (not blocking the event loop)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, input_path, output_path),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Return the current state of a job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    payload: dict = {
        "state": job["state"],
        "detail": job["detail"],
    }
    if job["state"] == "done" and job["output"]:
        payload["output_url"] = f"/download/{job_id}"

    return JSONResponse(payload)


@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """Serve the converted output video."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["state"] != "done" or job["output"] is None:
        raise HTTPException(status_code=409, detail="Video not ready yet.")

    output_path: Path = job["output"]
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="Output file missing.")

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=output_path.name,
    )


# ── Serve the frontend ───────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
