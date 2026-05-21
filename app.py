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
from pydantic import BaseModel

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="H2V - Horizontal to Vertical", version="1.0.0")

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
live_cut_jobs: dict[str, dict] = {}


# ── Request DTOs ──────────────────────────────────────────────────────────────
class LiveCutRequest(BaseModel):
    url: str
    seconds_ago: float
    duration: float


class ProcessVerticalRequest(BaseModel):
    video_id: str
    trim_start: float | None = None
    trim_end: float | None = None


# ── Background pipeline worker ───────────────────────────────────────────────
def _run_pipeline(job_id: str, input_path: Path, output_path: Path) -> None:
    """Segment → classify each segment → transform → concatenate."""
    try:
        print(f"\n[h2v] [{job_id}] Starting pipeline for: {input_path.name}")
        from core.segmenter import segment_video
        from core import ffmpeg_runner

        # ── Step 1: Segment & classify ────────────────────────────────────
        jobs[job_id]["detail"] = "Analysing video structure..."
        segments = segment_video(str(input_path))

        template_segs = [s for s in segments if s["type"] == "TEMPLATE" and s.get("template")]
        if not template_segs:
            raise RuntimeError("No classifiable template segments found.")

        print(f"[h2v] [{job_id}] {len(template_segs)} template segment(s) detected")

        # ── Step 2: Process each template segment ─────────────────────────
        temp_dir = UPLOAD_DIR / f"{job_id}_parts"
        temp_dir.mkdir(exist_ok=True)
        part_paths: list[Path] = []

        for i, seg in enumerate(template_segs):
            jobs[job_id]["detail"] = f"Converting segment {i + 1}/{len(template_segs)} ({seg['template']})..."
            
            part_path = temp_dir / f"part_{i:03d}.mp4"
            duration = seg['end'] - seg['start']
            
            transformer = importlib.import_module(f"templates.{seg['template']}.transformer")
            cmd = transformer.build_command(
                str(input_path), str(part_path), 
                start=seg["start"], duration=duration
            )
            ffmpeg_runner.run(cmd)
            part_paths.append(part_path)

        # ── Step 3: Concatenate (or move if single segment) ───────────────
        jobs[job_id]["detail"] = "Finalising..."
        if len(part_paths) == 1:
            part_paths[0].rename(output_path)
        else:
            concat_list = temp_dir / "concat.txt"
            concat_list.write_text(
                "\n".join(f"file '{p.resolve().as_posix()}'" for p in part_paths),
                encoding="utf-8",
            )
            ffmpeg_runner.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ])

        # Cleanup temp files
        for f in temp_dir.iterdir():
            f.unlink()
        temp_dir.rmdir()

        # ── Done ──────────────────────────────────────────────────────────
        jobs[job_id]["state"] = "done"
        jobs[job_id]["detail"] = "Conversion complete"
        jobs[job_id]["output"] = output_path
        print(f"[h2v] [{job_id}] OK Done -> {output_path.name}")

    except Exception as exc:
        jobs[job_id]["state"] = "error"
        jobs[job_id]["detail"] = str(exc)
        print(f"[h2v] [{job_id}] FAIL Error: {exc}")


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
        "detail": "Queued - starting pipeline...",
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


# ── Live Cut Background Worker ────────────────────────────────────────────────
def _run_live_cut(job_id: str, url: str, seconds_ago: float, duration: float, output_path: Path) -> None:
    """Download livestream segments concurrently and concatenate them."""
    try:
        print(f"\n[h2v] [{job_id}] Starting live cut extraction for: {url}")
        from core.live_cutter import extract_livestream_clip
        
        def update_progress(msg: str):
            live_cut_jobs[job_id]["detail"] = msg
            
        extract_livestream_clip(
            youtube_url=url,
            seconds_ago=seconds_ago,
            duration=duration,
            output_path=output_path,
            progress_callback=update_progress,
        )
        
        live_cut_jobs[job_id]["state"] = "done"
        live_cut_jobs[job_id]["detail"] = "Extraction complete"
        live_cut_jobs[job_id]["output"] = output_path
        print(f"[h2v] [{job_id}] OK Live cut done -> {output_path.name}")
    except Exception as exc:
        live_cut_jobs[job_id]["state"] = "error"
        live_cut_jobs[job_id]["detail"] = str(exc)
        print(f"[h2v] [{job_id}] FAIL Live cut error: {exc}")


# ── Live Cut Endpoints ────────────────────────────────────────────────────────

@app.post("/live-cut")
async def start_live_cut(req: LiveCutRequest):
    """Accept parameters for livestream clipping, launch download in background."""
    job_id = uuid.uuid4().hex[:12]
    output_path = UPLOAD_DIR / f"live_{job_id}.mp4"
    
    live_cut_jobs[job_id] = {
        "state": "processing",
        "detail": "Initializing live stream extraction...",
        "output": None,
    }
    
    thread = threading.Thread(
        target=_run_live_cut,
        args=(job_id, req.url, req.seconds_ago, req.duration, output_path),
        daemon=True,
    )
    thread.start()
    
    return JSONResponse({"job_id": job_id})


@app.get("/live-cut/status/{job_id}")
async def get_live_cut_status(job_id: str):
    """Poll progress status of live cut extraction."""
    job = live_cut_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Live cut job not found.")
        
    payload = {
        "state": job["state"],
        "detail": job["detail"],
    }
    if job["state"] == "done":
        payload["output_url"] = f"/live-cut/download/{job_id}"
        
    return JSONResponse(payload)


@app.get("/live-cut/download/{job_id}")
async def download_live_cut_video(job_id: str):
    """Serve the extracted horizontal live clip."""
    job = live_cut_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["state"] != "done" or job["output"] is None:
        raise HTTPException(status_code=409, detail="Live cut video not ready yet.")
        
    output_path = Path(job["output"])
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="Live cut output file missing.")
        
    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=output_path.name,
    )


@app.post("/process-vertical")
async def start_vertical_conversion(req: ProcessVerticalRequest):
    """Trim (optional) the horizontal clip and trigger the H2V transformation pipeline."""
    job = live_cut_jobs.get(req.video_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Source video not found.")
        
    if job["state"] != "done" or job["output"] is None:
        raise HTTPException(status_code=400, detail="Source video is not fully downloaded.")
        
    input_path = Path(job["output"])
    if not input_path.exists():
        raise HTTPException(status_code=500, detail="Source file is missing from uploads.")
        
    # Generate job ID for vertical pipeline
    job_id = uuid.uuid4().hex[:12]
    final_input_path = input_path
    
    # If trim requested, trim video using ffmpeg
    if req.trim_start is not None or req.trim_end is not None:
        trimmed_path = UPLOAD_DIR / f"trimmed_{job_id}.mp4"
        trim_start = req.trim_start or 0.0
        
        # Build ffmpeg command to trim
        cmd = ["ffmpeg", "-y"]
        if req.trim_start is not None:
            cmd.extend(["-ss", str(trim_start)])
        if req.trim_end is not None:
            cmd.extend(["-to", str(req.trim_end)])
            
        cmd.extend(["-i", str(input_path), "-c", "copy", str(trimmed_path)])
        
        try:
            from core import ffmpeg_runner
            ffmpeg_runner.run(cmd)
            final_input_path = trimmed_path
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to trim video using FFmpeg: {exc}")
            
    output_path = OUTPUT_DIR / f"{job_id}_vertical.mp4"
    
    jobs[job_id] = {
        "state": "processing",
        "detail": "Queued - starting pipeline...",
        "output": None,
    }
    
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, final_input_path, output_path),
        daemon=True,
    )
    thread.start()
    
    return JSONResponse({"job_id": job_id})


# ── Serve the frontend ───────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
