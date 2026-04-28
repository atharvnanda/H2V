"""
templates/breaking_news_split/transformer.py

Reads TEMPLATE_CONFIG (crop coordinates) and global settings (codec/CRF/etc.)
then builds a complete FFmpeg command list ready to hand off to core.ffmpeg_runner.

Filter chain overview
─────────────────────
  Split the input into 5 streams, each cropped and scaled. The bottom bar
  is split into two halves (top and bottom) to fill the exact remaining
  vertical space to reach 1920px evenly.

    [bottom_top] = crop → scale to output_width x (gap // 2)
    [headline]   = crop → scale to output_width
    [left]       = crop → scale to output_width
    [right]      = crop → scale to output_width
    [bottom_bot] = crop → scale to output_width x (gap - gap // 2)

  Stack vertically:
    [bottom_top][headline][left][right][bottom_bot] → vstack=inputs=5 → [out]

  Map [out] for video, pass audio through unchanged.
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


def _even(n: int) -> int:
    """Round down to nearest even number (h264 needs even dimensions)."""
    return n if n % 2 == 0 else n - 1


def _scaled_height(region: dict, target_w: int) -> int:
    """Predict the height FFmpeg's scale=target_w:-2 will produce."""
    h = region["h"] * target_w / region["w"]
    return _even(round(h))


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

    # ── Calculate scaled heights & gap budget ────────────────────────────────
    h_head  = _scaled_height(cfg["headline"],   out_w)
    h_left  = _scaled_height(cfg["left_panel"], out_w)
    h_right = _scaled_height(cfg["right_panel"], out_w)

    content_h = h_head + h_left + h_right
    gap = out_h - content_h

    gap_top = _even(gap // 2)
    gap_bot = gap - gap_top

    # ── Build filter_complex ─────────────────────────────────────────────────
    def crop_scale(region: dict, target_h: str) -> str:
        return (
            f"crop={region['w']}:{region['h']}:{region['x']}:{region['y']},"
            f" scale={out_w}:{target_h}"
        )

    headline_frag   = f"[0:v] {crop_scale(cfg['headline'], '-2')} [headline]"
    left_frag       = f"[0:v] {crop_scale(cfg['left_panel'], '-2')} [left]"
    right_frag      = f"[0:v] {crop_scale(cfg['right_panel'], '-2')} [right]"
    
    # Split the bottom bar into two halves
    bottom_top_frag = f"[0:v] {crop_scale(cfg['bottom_bar'], str(gap_top))} [bottom_top]"
    bottom_bot_frag = f"[0:v] {crop_scale(cfg['bottom_bar'], str(gap_bot))} [bottom_bot]"

    # vstack: all widths are out_w, total height is exactly out_h
    # setsar=1 forces square pixels so the 1080x1920 output displays correctly as 9:16
    vstack_frag = "[bottom_top][headline][left][right][bottom_bot] vstack=inputs=5, setsar=1 [out]"

    filter_complex = "; ".join([
        bottom_top_frag,
        headline_frag,
        left_frag,
        right_frag,
        bottom_bot_frag,
        vstack_frag,
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
