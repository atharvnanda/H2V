"""core/classifier.py — Hybrid template detection.

1. OpenCV geometry scoring  (header height + panel count)
2. Groq LLM tiebreaker      (only when top-2 scores are close)
"""
from __future__ import annotations

import base64
import os

import cv2
from dotenv import load_dotenv
from groq import Groq

from core.geometry import extract_frame, rank_templates

load_dotenv()

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def classify(video_path: str) -> str:
    """Return the best-matching template name for *video_path*."""
    ranked = rank_templates(video_path)
    if not ranked:
        raise RuntimeError("No templates found.")

    top = ranked[0]       # (name, score, desc)
    runner = ranked[1] if len(ranked) > 1 else None

    # Clear winner → skip LLM entirely
    if runner is None or top[1] > runner[1] * 1.3:
        return top[0]

    # Ambiguous → LLM picks between top 2
    print(f"  [tiebreak] {top[0]} ({top[1]:.0f}) vs {runner[0]} ({runner[1]:.0f}) → asking LLM")
    return _llm_tiebreak(video_path, top, runner)


def _llm_tiebreak(
    video_path: str,
    a: tuple[str, float, str],
    b: tuple[str, float, str],
) -> str:
    """Ask LLM to choose between two candidate templates."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set.")

    frame = extract_frame(video_path)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf).decode()

    prompt = (
        f"This broadcast frame matches one of these two layouts:\n\n"
        f"A) {a[0]}: {a[2]}\n"
        f"B) {b[0]}: {b[2]}\n\n"
        f"Reply with ONLY the exact name: {a[0]} or {b[0]}"
    )

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=32,
    )

    result = resp.choices[0].message.content.strip()
    return result if result in (a[0], b[0]) else a[0]  # fallback to top scorer
