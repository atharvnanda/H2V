# H2V: Horizontal to Vertical Converter

## Project Context
H2V is a web application and processing pipeline designed to convert standard widescreen (16:9) broadcast news videos into vertical (9:16) format. It uses geometric algorithms and AI/LLM models to detect layout templates (such as splitscreen panels, studio anchors, and headers) and crops/arranges panels dynamically.

## Architecture Overview
H2V consists of a FastAPI backend and a vanilla HTML5/JS frontend.
- **Backend (`app.py`)**: Hosts API endpoints for uploading videos, clipping livestreams, polling status, and downloading vertical output.
- **Livestream Scraper (`core/live_cutter.py`)**: Fetches segments from live DVR buffer using `yt-dlp` and `ThreadPoolExecutor`, merging them with FFmpeg.
- **Segmenter (`core/segmenter.py`)**: Samples video frames and identifies stable layout template chunks.
- **Classifier (`core/classifier.py`)**: Uses hybrid template detection combining geometry scoring, structural boundaries, and Groq LLM fallback queries.
- **Templates (`templates/`)**: Contains crop coordinates and transformer commands for rendering different screen layouts (e.g. `2panel_breaking`).

## Directory Structure
- `app.py`: FastAPI server entrypoint.
- `core/`: Main backend logic.
  - `live_cutter.py`: YouTube live DVR clip extractor.
  - `segmenter.py`: Sampling and template segmentation.
  - `classifier.py`: Geometry and LLM template classification.
  - `geometry.py`: Screen region layout analysis.
  - `ffmpeg_runner.py`: FFmpeg execution wrapper.
- `frontend/`: Web user interface.
  - `index.html`: Unified single-page interface with drag-drop and live range trimmer.
- `templates/`: Crop definitions and instructions for different layouts.
- `uploads/`: Temporary store for uploaded and processed horizontal clips.
- `output/`: Folder containing final horizontal-to-vertical conversion results.

## Local Setup & Execution
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up environment variables in `.env` file:
   - `GROQ_API_KEY`: API key for Groq LLM classification fallback.
3. Start the development server:
   ```bash
   python -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```
