"""core/classifier.py — Hybrid template detection.

1. OpenCV geometry scoring  (header height + panel count)
2. Boundary count tiebreaker (confirmed structural dividers, only between multi-panel templates)
3. Groq LLM tiebreaker      (only when geometry + boundaries are both tied)
"""
from __future__ import annotations

import base64
import os

import cv2
import numpy as np
from dotenv import load_dotenv
from groq import Groq

from core.geometry import extract_frame, rank_templates

load_dotenv()

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def classify(video_path: str = None, *, frame: np.ndarray = None) -> str:
    """Return the best-matching template name. Pass either video_path or frame."""
    ranked = rank_templates(video_path, frame=frame)
    if not ranked:
        raise RuntimeError("No templates found.")

    top = ranked[0]       # (name, score, desc, n_confirmed)
    runner = ranked[1] if len(ranked) > 1 else None

    # Clear winner — score gap > 15% → trust geometry, skip everything
    if runner is None or top[1] > runner[1] * 1.15:
        return top[0]

    # Scores are close → try confirmed boundary count as tiebreaker ONLY when
    # both candidates have boundaries to compare (i.e. neither is fullscreen).
    # Fullscreen has n_confirmed=0 by design, so comparing it against a
    # multi-panel template that confirmed 1+ boundaries is unfair — the score
    # already encodes the right answer in that case.
    top_confirmed = top[3]
    runner_confirmed = runner[3]
    both_have_boundaries = top_confirmed > 0 and runner_confirmed > 0
    if both_have_boundaries and top_confirmed != runner_confirmed:
        winner = top[0] if top_confirmed > runner_confirmed else runner[0]
        print(f"  [tiebreak] {top[0]} ({top[1]:.0f}, b={top_confirmed}) vs "
              f"{runner[0]} ({runner[1]:.0f}, b={runner_confirmed}) → boundary count wins: {winner}")
        return winner

    # Boundary count tied (or one is fullscreen) → ask LLM
    print(f"  [tiebreak] {top[0]} ({top[1]:.0f}) vs {runner[0]} ({runner[1]:.0f}) → asking LLM")
    return _llm_tiebreak(video_path, frame, top, runner)


def _llm_tiebreak(
    video_path: str | None,
    frame: np.ndarray | None,
    a: tuple[str, float, str, int],
    b: tuple[str, float, str, int],
) -> str:
    """Ask LLM to choose between two candidate templates."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set.")

    if frame is None:
        frame = extract_frame(video_path)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf).decode()

    prompt = (
        f"You are analyzing an Indian broadcast news frame to identify its layout template.\n\n"
        f"TASK: Look at the video panel area BELOW the headline/header text. "
        f"Count how many distinct vertical video columns are separated by visible dividing lines. "
        f"Do NOT count sub-panels stacked within the same column.\n\n"
        f"CANDIDATE TEMPLATES:\n"
        f"A) {a[0]}: {a[2]}\n"
        f"B) {b[0]}: {b[2]}\n\n"
        f"Step 1: Count the vertical video columns you see below the header.\n"
        f"Step 2: Match that count to the correct template.\n"
        f"Step 3: Reply with ONLY the exact template name — either '{a[0]}' or '{b[0]}'. No other text."
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
        max_tokens=50,
    )

    result = resp.choices[0].message.content.strip()
    # Extract exact template name even if LLM included extra reasoning text
    for candidate in (a[0], b[0]):
        if candidate in result:
            return candidate
    return a[0]  # fallback to top geometry scorer
