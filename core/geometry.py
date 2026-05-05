"""core/geometry.py — Config-projection template scoring via OpenCV."""
from __future__ import annotations
import importlib
from pathlib import Path
import cv2
import numpy as np

TEMPLATES_DIR = Path(__file__).parents[1] / "templates"


def extract_frame(video_path: str) -> np.ndarray:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int((cap.get(cv2.CAP_PROP_FPS) or 25)))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("Failed to read frame.")
    return cv2.resize(frame, (1280, 720)) if frame.shape[:2] != (720, 1280) else frame


def _detect_header_bottom(gray: np.ndarray) -> int:
    cutoff = int(gray.shape[0] * 0.45)
    sobel = np.abs(cv2.Sobel(gray[:cutoff], cv2.CV_64F, 0, 1, ksize=3))
    profile = np.convolve(sobel.mean(axis=1), np.ones(5) / 5, mode="same")
    idx = int(np.argmax(profile))
    if profile[idx] < 15:  # Too weak to be a deliberate graphic boundary
        return 0
    return idx


def _detect_bottom_bar_top(gray: np.ndarray) -> int:
    cutoff = int(gray.shape[0] * 0.55)
    zone = gray[cutoff:]
    sobel = np.abs(cv2.Sobel(zone, cv2.CV_64F, 0, 1, ksize=3))
    profile = np.convolve(sobel.mean(axis=1), np.ones(5) / 5, mode="same")
    idx = int(np.argmax(profile))
    if profile[idx] < 15:  # Too weak to be a deliberate graphic boundary
        return gray.shape[0]  # Fallback to bottom of frame (720)
    return idx + cutoff


def _extract_panel_x_boundaries(cfg: dict) -> list[int]:
    """Derive vertical split x-positions from config panel regions."""
    skip = {"source_width", "source_height", "headline", "bottom_bar"}
    panels = [v for k, v in cfg.items() if k not in skip and isinstance(v, dict) and "x" in v]
    panels.sort(key=lambda p: p["x"])
    # Boundary = midpoint between one panel's right edge and next panel's left edge
    return [(panels[i]["x"] + panels[i]["w"] + panels[i + 1]["x"]) // 2
            for i in range(len(panels) - 1)]


def _boundary_hit_rate(gray: np.ndarray, y_top: int, y_bot: int, x_positions: list[int]) -> float:
    """What fraction of expected boundaries have actual edges? (0.0–1.0)"""
    if not x_positions:
        # Fullscreen: A pure fullscreen layout has no vertical split lines.
        # By always returning 1.0, it gets max boundary score and wins if no other 
        # templates get high boundary hits.
        return 1.0

    zone = gray[y_top:y_bot, :]
    sobel = np.abs(cv2.Sobel(zone, cv2.CV_64F, 1, 0, ksize=3))
    
    hits = 0
    for x in x_positions:
        # Check a narrow window around the expected x position
        x_start = max(0, x - 3)
        x_end = min(sobel.shape[1], x + 4)
        window = sobel[:, x_start:x_end]
        
        # For a structural line, there should be a strong edge along most of the vertical span.
        # Find the max edge strength in the window for each row.
        row_max = window.max(axis=1)
        
        # A true structural line should cover most of the height. 
        # We use > 0.40 (40%) to allow for overlay graphics (names, 'Live' bugs) that might cover parts of the line.
        # This is relaxed from 60% so templates with more panels don't lose points due to large overlays.
        if (row_max > 30).mean() > 0.40:
            hits += 1

    return hits / len(x_positions)


def rank_templates(video_path: str = None, *, frame: np.ndarray = None) -> list[tuple[str, float, str]]:
    if frame is None:
        frame = extract_frame(video_path)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    m_header = _detect_header_bottom(gray)
    m_bottom = _detect_bottom_bar_top(gray)
    print(f"  [geometry] header_bottom={m_header}px, bottom_top={m_bottom}px")

    scored: list[tuple[str, float, str]] = []
    for folder in sorted(TEMPLATES_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"templates.{folder.name}.config")
            cfg = getattr(mod, "TEMPLATE_CONFIG", {})
            desc = getattr(mod, "DETECTION_DESCRIPTION", "")
        except Exception:
            continue

        exp_header = cfg.get("headline", {}).get("h", 0)
        exp_bottom = cfg.get("bottom_bar", {}).get("y", 0)
        boundaries = _extract_panel_x_boundaries(cfg)
        panel_top = (exp_header or m_header) + 5
        bottom_y = exp_bottom or m_bottom

        # Header score (0–100): how close is measured header to expected
        if exp_header > 0:
            h_score = max(0.0, 100 - abs(m_header - exp_header))
        elif m_header < 50:
            h_score = 80.0
        else:
            h_score = 0.0

        # Bottom score (0–100): how close is measured bottom to expected
        if exp_bottom > 0:
            bot_score = max(0.0, 100 - abs(m_bottom - exp_bottom))
        elif m_bottom > 670:
            bot_score = 80.0
        else:
            bot_score = 0.0

        # Boundary score (0–100): % of config boundaries confirmed in frame
        hit_rate = _boundary_hit_rate(gray, panel_top, bottom_y, boundaries)
        b_score = hit_rate * 100
        
        # Complexity Bonus: Break mathematical ties by rewarding templates 
        # that successfully match MORE structural boundaries. 
        # +10 points per successfully confirmed boundary.
        if boundaries:
            b_score += (hit_rate * len(boundaries)) * 10

        total = h_score + bot_score + b_score
        scored.append((folder.name, total, desc))

    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"  [scores] {[(n, f'{s:.0f}') for n, s, _ in scored]}")
    return scored
