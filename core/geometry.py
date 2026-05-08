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
    if profile[idx] < 10:  # Too weak to be a deliberate graphic boundary
        return 0
    return idx


def _detect_bottom_bar_top(gray: np.ndarray) -> int:
    cutoff = int(gray.shape[0] * 0.55)
    zone = gray[cutoff:]
    sobel = np.abs(cv2.Sobel(zone, cv2.CV_64F, 0, 1, ksize=3))
    profile = np.convolve(sobel.mean(axis=1), np.ones(5) / 5, mode="same")
    idx = int(np.argmax(profile))
    if profile[idx] < 10:  # Too weak to be a deliberate graphic boundary
        return gray.shape[0]  # Fallback to bottom of frame (720)
    return idx + cutoff


def _extract_panel_x_boundaries(cfg: dict) -> list[int]:
    """Derive vertical split x-positions from config panel regions."""
    skip = {"source_width", "source_height", "headline", "bottom_bar", "graphics", "footer"}
    panels = [v for k, v in cfg.items() if k not in skip and isinstance(v, dict) and "x" in v]
    panels.sort(key=lambda p: p["x"])
    # Boundary = midpoint between one panel's right edge and next panel's left edge
    return [(panels[i]["x"] + panels[i]["w"] + panels[i + 1]["x"]) // 2
            for i in range(len(panels) - 1)]


def _is_structural_divider(
    sobel_full: np.ndarray,
    profile: np.ndarray,
    x: int,
    min_span_fraction: float = 0.55,
    max_half_width: int = 6,
) -> bool:
    """Return True only if the edge at x looks like a real panel divider line.

    Two checks must BOTH pass:

    1. Vertical span continuity — a structural divider runs the full height of
       the content zone.  Text/graphic edges only exist where the glyph or shape
       is, typically 10-20% of the zone height.  We require ≥ min_span_fraction
       of rows in a 5-px-wide column strip to carry a strong horizontal Sobel
       response (> 20).  Real dividers easily hit 0.80+; bold letter strokes
       rarely exceed 0.20.

    2. Width / narrowness — a physical 2-5 px line produces a very narrow spike
       in the column-averaged Sobel profile.  We measure the half-max width on
       each side of the peak.  Text strokes are 15-30 px wide; divider lines
       are typically ≤ 6 px wide on each side (total ≤ 12 px).
    """
    profile_len = len(profile)

    # --- Check 1: vertical span continuity ---
    x_lo = max(0, x - 2)
    x_hi = min(sobel_full.shape[1], x + 3)          # 5-px-wide strip
    col_strip = sobel_full[:, x_lo:x_hi].max(axis=1) # per-row max response
    span_fraction = (col_strip > 20).mean()
    if span_fraction < min_span_fraction:
        return False

    # --- Check 2: peak width (half-max width on each side) ---
    peak_val = profile[x]
    half_max = peak_val / 2.0

    # Walk left until profile drops below half-max (or we hit the boundary)
    left_width = 0
    for i in range(1, 40):
        if x - i < 0 or profile[x - i] < half_max:
            left_width = i - 1
            break
    else:
        left_width = 39  # never dropped — peak is very wide

    # Walk right
    right_width = 0
    for i in range(1, 40):
        if x + i >= profile_len or profile[x + i] < half_max:
            right_width = i - 1
            break
    else:
        right_width = 39

    if left_width > max_half_width or right_width > max_half_width:
        return False

    return True


def _boundary_hit_rate(gray: np.ndarray, y_top: int, y_bot: int, x_positions: list[int]) -> float:
    """What fraction of expected boundaries have actual edges? (0.0–1.0)

    For multi-panel templates each expected boundary x must pass TWO structural
    tests before counting as a hit:
      • vertical span continuity  — edge spans ≥ 55% of the content-zone height
      • peak narrowness           — half-max width ≤ 6 px on each side

    This rejects false positives from text, logos, and geometric graphics (which
    create strong but short-lived or wide Sobel responses) while keeping real
    thin panel-divider lines (which run full-height and produce narrow spikes).
    """
    if not x_positions:
        # Fullscreen: reward LOW internal edge density (no vertical splits expected)
        zone = gray[max(y_top, 50):min(y_bot, 520), 100:-100]
        density = np.abs(cv2.Sobel(zone, cv2.CV_64F, 1, 0, ksize=3)).mean()
        return 1.0 if density < 12 else 0.0

    # Compute Sobel once for the content zone — reused by both the profile and
    # the per-column span check so we don't run it twice.
    zone = gray[y_top:y_bot, :]
    sobel_zone = np.abs(cv2.Sobel(zone, cv2.CV_64F, 1, 0, ksize=3))

    # Column-averaged profile (smoothed) — same as before; used for the peak
    # amplitude pre-filter and the width check.
    profile = np.convolve(sobel_zone.mean(axis=0), np.ones(5) / 5, mode="same")

    # 85th-percentile threshold: keeps the cheap pre-filter the same as before.
    threshold = np.percentile(profile[30:-30], 85)

    hits = 0
    for x in x_positions:
        if x < 5 or x >= len(profile) - 5:
            continue

        # Pre-filter: must at least be a local peak above the global threshold.
        # This is the original check — cheap, eliminates most non-edges quickly.
        if profile[x - 3:x + 4].max() <= threshold:
            continue

        # Structural divider tests: both must pass.
        if _is_structural_divider(sobel_zone, profile, x):
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
        # NOTE: No complexity bonus — it causes N-panel templates to systematically
        # outscore (N-1)-panel templates when both hit 100%, which is wrong.

        print(f"    {folder.name}: h={h_score:.0f} bot={bot_score:.0f} b={b_score:.0f}(hit={hit_rate:.2f}, n={len(boundaries)})")

        total = h_score + bot_score + b_score
        scored.append((folder.name, total, desc))

    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"  [scores] {[(n, f'{s:.0f}') for n, s, _ in scored]}")
    return scored
