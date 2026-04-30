"""
templates/fullscreen_breaking/transformer.py

Reads global settings and builds an FFmpeg command to convert a 16:9 
video to 9:16 by stretching it to 1080x1480 and padding the rest.

Filter chain overview
─────────────────────
  [0:v] scale to 1080:1480 → pad to 1080:1920 (centered) → setsar=1 → [out]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import TEMPLATE_CONFIG

# Path to global settings relative to this file: ../../config/settings.yaml
_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_command(input_path: str, output_path: str) -> list[str]:
    """Construct and return the full FFmpeg argument list."""
    settings = _load_settings()["output"]

    out_w: int = settings["width"]          # 1080
    out_h: int = settings["height"]         # 1920
    codec: str = settings["codec"]          # libx264
    crf: int   = settings["crf"]            # 18
    preset: str = settings["preset"]        # fast
    audio_codec: str = settings["audio_codec"]  # copy
    pad_color: str = settings["pad_color"]  # 0xAA0000

    # ── Build filter_complex ─────────────────────────────────────────────────
    # Stretch to 1080x1480, then pad to out_w x out_h centered
    filter_complex = (
        f"[0:v] scale=1080:1480, "
        f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:{pad_color}, "
        f"setsar=1 [out]"
    )

    # ── Assemble full command ────────────────────────────────────────────────
    cmd: list[str] = [
        "ffmpeg",
        "-y",                         # overwrite output without prompting
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",              # use our filtered video stream
        "-map", "0:a?",               # pass audio through if present
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", audio_codec,
        output_path,
    ]

    return cmd
