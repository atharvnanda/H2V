"""
templates/breaking_news_split/transformer.py

Reads TEMPLATE_CONFIG (crop coordinates) and global settings (codec/CRF/etc.)
then builds a complete FFmpeg command list ready to hand off to core.ffmpeg_runner.

Filter chain overview
─────────────────────
  Split the input into 3 streams, each cropped → scaled → padded with a
  share of the total gap (filled with pad_color):

    [headline] = crop → scale → pad (gap_top above)
    [left]     = crop → scale → pad (gap_mid1 above)
    [right]    = crop → scale → pad (gap_mid2 above, gap_bottom below)

  Stack vertically:
    [headline][left][right] → vstack=inputs=3 → [out]

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
    total_gap = out_h - content_h

    # Split gap into 4 positions: top | headline | mid1 | left | mid2 | right | bottom
    gap_base = _even(total_gap // 4)
    gap_top  = gap_base
    gap_mid1 = gap_base
    gap_mid2 = gap_base
    gap_bot  = total_gap - gap_top - gap_mid1 - gap_mid2  # absorbs rounding remainder

    # ── Build filter_complex ─────────────────────────────────────────────────
    #   Each panel: crop → scale to out_w (exact height) → pad to add its gap portion.
    #   Then vstack=inputs=3 produces exactly out_h.

    def crop_scale(region: dict) -> str:
        return (
            f"crop={region['w']}:{region['h']}:{region['x']}:{region['y']},"
            f" scale={out_w}:-2"
        )

    # headline: gap_top pixels of padding above the content
    canvas_head = h_head + gap_top
    headline_frag = (
        f"[0:v] {crop_scale(cfg['headline'])},"
        f" pad={out_w}:{canvas_head}:0:{gap_top}:{pad_color} [headline]"
    )

    # left panel: gap_mid1 pixels of padding above the content
    canvas_left = h_left + gap_mid1
    left_frag = (
        f"[0:v] {crop_scale(cfg['left_panel'])},"
        f" pad={out_w}:{canvas_left}:0:{gap_mid1}:{pad_color} [left]"
    )

    # right panel: gap_mid2 above + gap_bot below
    canvas_right = h_right + gap_mid2 + gap_bot
    right_frag = (
        f"[0:v] {crop_scale(cfg['right_panel'])},"
        f" pad={out_w}:{canvas_right}:0:{gap_mid2}:{pad_color} [right]"
    )

    # vstack: all widths are out_w, total height = canvas_head + canvas_left + canvas_right = out_h
    vstack_frag = "[headline][left][right] vstack=inputs=3 [out]"

    filter_complex = "; ".join([
        headline_frag,
        left_frag,
        right_frag,
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
