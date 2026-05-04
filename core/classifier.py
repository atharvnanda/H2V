"""
core/classifier.py — Auto-detect template from a video frame using Groq vision API.

Requires:
  - GROQ_API_KEY environment variable
  - ffmpeg on PATH
  - groq Python package  (pip install groq)
"""
from __future__ import annotations

import base64
import importlib
import os
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from groq import Groq

# ── Paths ─────────────────────────────────────────────────────────────────────
PROMPT_PATH   = Path(__file__).parent / "prompts" / "classify.txt"
TEMPLATES_DIR = Path(__file__).parents[1] / "templates"
MODEL         = "meta-llama/llama-4-scout-17b-16e-instruct"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_frame(video_path: str) -> bytes:
    """Return JPEG bytes for a single frame extracted at t=1 s via FFmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", "1",
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            tmp_path,
        ],
        capture_output=True,
        check=True,
    )
    data = Path(tmp_path).read_bytes()
    Path(tmp_path).unlink(missing_ok=True)
    return data


def _load_descriptions() -> dict[str, str]:
    """Return {folder_name: DETECTION_DESCRIPTION} for every valid template."""
    result: dict[str, str] = {}
    for folder in sorted(TEMPLATES_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        try:
            mod  = importlib.import_module(f"templates.{folder.name}.config")
            desc = getattr(mod, "DETECTION_DESCRIPTION", None)
            if desc:
                result[folder.name] = str(desc).strip()
        except Exception:
            continue
    return result


def _build_prompt(descriptions: dict[str, str]) -> str:
    """Fill the classify.txt template with the description block."""
    block = "\n".join(f"- {name}: {desc}" for name, desc in descriptions.items())
    return PROMPT_PATH.read_text(encoding="utf-8").replace("{template_descriptions}", block)


# ── Public API ────────────────────────────────────────────────────────────────

def classify(video_path: str) -> str:
    """
    Detect and return the best-matching template folder name for *video_path*.

    Raises
    ------
    RuntimeError
        If no templates have DETECTION_DESCRIPTION defined.
    ValueError
        If the model returns a name that does not match any known template.
    subprocess.CalledProcessError
        If FFmpeg fails to extract a frame.
    """
    descriptions = _load_descriptions()
    if not descriptions:
        raise RuntimeError(
            "No templates have DETECTION_DESCRIPTION defined. "
            "Add the string to each templates/<name>/config.py."
        )

    prompt = _build_prompt(descriptions)
    frame  = _extract_frame(video_path)
    b64    = base64.b64encode(frame).decode()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file or environment.")

    client = Groq(api_key=api_key)
    resp   = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",      "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        max_tokens=32,
    )

    result = resp.choices[0].message.content.strip()

    if result not in descriptions:
        raise ValueError(
            f"[classifier] Model returned '{result}', expected one of: "
            + ", ".join(descriptions.keys())
        )

    return result
