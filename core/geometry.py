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
    return int(np.argmax(profile))


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
        # Fullscreen: reward LOW internal edge density
        zone = gray[max(y_top, 50):min(y_bot, 520), 100:-100]
        density = np.abs(cv2.Sobel(zone, cv2.CV_64F, 1, 0, ksize=3)).mean()
        return 1.0 if density < 12 else 0.0

    zone = gray[y_top:y_bot, :]
    sobel = np.abs(cv2.Sobel(zone, cv2.CV_64F, 1, 0, ksize=3))
    profile = np.convolve(sobel.mean(axis=0), np.ones(5) / 5, mode="same")
    threshold = np.percentile(profile[30:-30], 75)

    hits = sum(1 for x in x_positions if 5 <= x < len(profile) - 5 and profile[x - 3:x + 4].max() > threshold)
    return hits / len(x_positions)


def rank_templates(video_path: str = None, *, frame: np.ndarray = None) -> list[tuple[str, float, str]]:
    if frame is None:
        frame = extract_frame(video_path)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    m_header = _detect_header_bottom(gray)
    print(f"  [geometry] header_bottom={m_header}px")

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
        boundaries = _extract_panel_x_boundaries(cfg)
        bottom_y = cfg.get("bottom_bar", {}).get("y", 520)
        panel_top = (exp_header or m_header) + 5

        # Header score (0–100): how close is measured header to expected
        if exp_header > 0:
            h_score = max(0.0, 100 - abs(m_header - exp_header))
        elif m_header < 50:
            h_score = 80.0
        else:
            h_score = 0.0

        # Boundary score (0–100): % of config boundaries confirmed in frame
        b_score = _boundary_hit_rate(gray, panel_top, bottom_y, boundaries) * 100

        total = h_score + b_score
        scored.append((folder.name, total, desc))

    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"  [scores] {[(n, f'{s:.0f}') for n, s, _ in scored]}")
    return scored
