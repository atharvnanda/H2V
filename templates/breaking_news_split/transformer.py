"""
templates/breaking_news_split/transformer.py

Reads TEMPLATE_CONFIG (crop coordinates) and global settings (codec/CRF/etc.)
then builds a complete FFmpeg command list ready to hand off to core.ffmpeg_runner.

Filter chain overview
─────────────────────
  Split the input into 3 streams:
    [headline] = crop → scale to output_width
    [left]     = crop → scale to output_width
    [right]    = crop → scale to output_width

  Stack vertically:
    [headline][left][right] → vstack=inputs=3 → [stacked]

  Pad to exact output dimensions (gap filled with pad_color from settings):
    [stacked] → pad=output_width:output_height:x_offset:y_offset:color → [out]

  Map [out] for video, pass audio through unchanged.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml

from .config import TEMPLATE_CONFIG

# Path to global settings relative to this file: ../../config/settings.yaml
_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _crop_scale_fragment(label: str, region: dict, out_w: int) -> str:
    """Return a filter fragment that crops *region* and scales width to *out_w*."""
    x, y, w, h = region["x"], region["y"], region["w"], region["h"]
    # scale=out_w:-2  → width fixed, height auto-calculated and rounded to even
    return f"[0:v] crop={w}:{h}:{x}:{y}, scale={out_w}:-2 [{label}]"


def build_command(input_path: str, output_path: str) -> list[str]:
    """Construct and return the full FFmpeg argument list.

    Parameters
    ----------
    input_path:  Absolute path to the source 16:9 video.
    output_path: Absolute path for the 9:16 output video.

    Returns
    -------
    list[str]  Ready to pass directly to subprocess / ffmpeg_runner.run().
    """
    cfg = TEMPLATE_CONFIG
    settings = _load_settings()["output"]

    out_w: int = settings["width"]          # 1080
    out_h: int = settings["height"]         # 1920
    codec: str = settings["codec"]          # libx264
    crf: int   = settings["crf"]            # 18
    preset: str = settings["preset"]        # fast
    audio_codec: str = settings["audio_codec"]  # copy
    pad_color: str = settings["pad_color"]  # 0xAA0000

    # ── Build filter_complex ─────────────────────────────────────────────────
    # Each crop/scale line uses a distinct input pad label.
    headline_frag = _crop_scale_fragment("headline", cfg["headline"],  out_w)
    left_frag     = _crop_scale_fragment("left",     cfg["left_panel"], out_w)
    right_frag    = _crop_scale_fragment("right",    cfg["right_panel"], out_w)

    # vstack requires all inputs to have the same width (guaranteed by scale above)
    vstack_frag = "[headline][left][right] vstack=inputs=3 [stacked]"

    # pad: center horizontally, align to top vertically; fill gap at bottom with pad_color
    pad_frag = (
        f"[stacked] pad=w={out_w}:h={out_h}"
        f":x=(ow-iw)/2:y=0"
        f":color={pad_color} [out]"
    )

    filter_complex = "; ".join([
        headline_frag,
        left_frag,
        right_frag,
        vstack_frag,
        pad_frag,
    ])

    # ── Assemble full command ────────────────────────────────────────────────
    cmd: list[str] = [
        "ffmpeg",
        "-y",                         # overwrite output without prompting
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",              # use our filtered video stream
        "-map", "0:a?",               # pass audio through if present (? = optional)
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", audio_codec,
        output_path,
    ]

    return cmd
