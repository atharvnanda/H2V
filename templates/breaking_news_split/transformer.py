"""
templates/breaking_news_split/transformer.py

Reads TEMPLATE_CONFIG (crop coordinates) and global settings (codec/CRF/etc.)
then builds a complete FFmpeg command list ready to hand off to core.ffmpeg_runner.

Filter chain overview
─────────────────────
  Split the input into 4 streams. The headline and bottom bar maintain their 
  aspect ratios, and the remaining vertical space is divided between the 
  left and right panels (which are stretched to fill the space).

    [headline] = crop → scale to output_width
    [left]     = crop → scale to output_width x (remaining_height // 2)
    [right]    = crop → scale to output_width x (remaining_height - left_height)
    [bottom]   = crop → scale to output_width

  Stack vertically:
    [headline][left][right][bottom] → vstack=inputs=4, setsar=1 → [out]

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
    h_bot   = _scaled_height(cfg["bottom_bar"], out_w)
    h_remaining = out_h - h_head - h_bot
    h_left = _even(h_remaining // 2)
    h_right = h_remaining - h_left

    # ── Build filter_complex ─────────────────────────────────────────────────
    def crop_scale(region: dict, target_h: str) -> str:
        return (
            f"crop={region['w']}:{region['h']}:{region['x']}:{region['y']},"
            f" scale={out_w}:{target_h}"
        )

    headline_frag   = f"[0:v] {crop_scale(cfg['headline'], '-2')} [headline]"
    left_frag       = f"[0:v] {crop_scale(cfg['left_panel'], str(h_left))} [left]"
    right_frag      = f"[0:v] {crop_scale(cfg['right_panel'], str(h_right))} [right]"
    bottom_frag     = f"[0:v] {crop_scale(cfg['bottom_bar'], '-2')} [bottom]"

    # vstack: all widths are out_w, total height is exactly out_h
    # setsar=1 forces square pixels so the 1080x1920 output displays correctly as 9:16
    vstack_frag = "[headline][left][right][bottom] vstack=inputs=4, setsar=1 [out]"

    filter_complex = "; ".join([
        headline_frag,
        left_frag,
        right_frag,
        bottom_frag,
        vstack_frag,
    ])
    
    # === Commented out old 5-stack filter complex ===
    # filter_complex = "; ".join([
    #     bottom_top_frag,
    #     headline_frag,
    #     left_frag,
    #     right_frag,
    #     bottom_bot_frag,
    #     vstack_frag,
    # ])

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
