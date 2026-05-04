"""
templates/studio_3_panels/transformer.py

Reads TEMPLATE_CONFIG and builds an FFmpeg command.
Stacks 5 elements vertically:
  [headline]
  [left]
  [mid]
  [right]
  [bottom]
Headline and bottom_bar are scaled proportionally, while the three studio
panels share the remaining vertical space equally.
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
    cfg = TEMPLATE_CONFIG
    settings = _load_settings()["output"]

    out_w: int = settings["width"]          # 1080
    out_h: int = settings["height"]         # 1920
    codec: str = settings["codec"]          # libx264
    crf: int   = settings["crf"]            # 18
    preset: str = settings["preset"]        # fast
    audio_codec: str = settings["audio_codec"]  # copy

    # ── Calculate scaled heights & gap budget ────────────────────────────────
    h_head = _scaled_height(cfg["headline"], out_w)
    h_bottom_bar = _scaled_height(cfg["bottom_bar"], out_w)

    # Remaining vertical space is shared equally among the 3 panels
    panels_total = out_h - h_head - h_bottom_bar
    panel_h = _even(panels_total // 3)
    panel_h_last = panels_total - panel_h * 2  # absorbs rounding remainder

    # ── Build filter_complex ─────────────────────────────────────────────────
    def crop_scale(region: dict, target_h: str) -> str:
        return (
            f"crop={region['w']}:{region['h']}:{region['x']}:{region['y']},"
            f" scale={out_w}:{target_h}"
        )

    headline_frag   = f"[0:v] {crop_scale(cfg['headline'], '-2')} [headline]"
    left_frag       = f"[0:v] {crop_scale(cfg['studio_left'], str(panel_h))} [left]"
    mid_frag        = f"[0:v] {crop_scale(cfg['studio_mid'], str(panel_h))} [mid]"
    right_frag      = f"[0:v] {crop_scale(cfg['studio_right'], str(panel_h_last))} [right]"
    bottom_frag     = f"[0:v] {crop_scale(cfg['bottom_bar'], '-2')} [bottom]"

    # setsar=1 forces square pixels so the 1080x1920 output displays correctly as 9:16
    vstack_frag = "[headline][left][mid][right][bottom] vstack=inputs=5, setsar=1 [out]"

    filter_complex = "; ".join([
        headline_frag,
        left_frag,
        mid_frag,
        right_frag,
        bottom_frag,
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
