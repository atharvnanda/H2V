# ---------------------------------------------------------------------------
# Template: 2panel_breaking
# ---------------------------------------------------------------------------

TEMPLATE_CONFIG: dict = {
    # ── Source video resolution ──────────────────────────────────────────────
    "source_width": 1280,
    "source_height": 720,

    # ── Region 1: Headline / Breaking News bar ────────────────────────────────
    # Spans full width; starts at top of frame.
    "headline": {
        "x": 0,
        "y": 0,
        "w": 1280,
        "h": 250,           # ← tune this: y-coord where panels start
    },

    # ── Region 2: Left panel (anchor / reporter) ──────────────────────────────
    "left_panel": {
        "x": 45,
        "y": 250,           # must match headline.h
        "w": 595,
        "h": 270,           # ← tune this: panel height (520 - 250)
    },

    # ── Region 3: Right panel (event / b-roll) ────────────────────────────────
    "right_panel": {
        "x": 638,           # must match left_panel.w
        "y": 250,           # must match headline.h
        "w": 595,           # 1280 - 638
        "h": 270,           # must match left_panel.h
    },

    # ── Region 4: Bottom animation/background ─────────────────────────────────
    "bottom_bar": {
        "x": 0,
        "y": 521,
        "w": 1280,
        "h": 199,           # 720 - 521
    },
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
DETECTION_DESCRIPTION = "TWO-panel BREAKING NEWS layout. Has a MASSIVE 250px red header with huge white 'BREAKING NEWS' text taking up ~35% of the frame. Below it are exactly TWO equal 595x270px SHORT panels side-by-side. 199px bottom bar. Panels are SHORT (270px) because the header is so large. Red geometric background. NOT a studio layout."
