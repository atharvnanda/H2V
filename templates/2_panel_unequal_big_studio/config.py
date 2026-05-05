# ---------------------------------------------------------------------------
# Template: 2_panel_unequal_big_studio
# ---------------------------------------------------------------------------
# All pixel values are for a 1280×720 source frame.
# ---------------------------------------------------------------------------

TEMPLATE_CONFIG: dict = {
    "source_width": 1280,
    "source_height": 720,

    "headline": {
        "x": 0,
        "y": 0,
        "w": 1280,
        "h": 122,
    },

    "studio_left": {
        "x": 48,
        "y": 127,
        "w": 449,
        "h": 481,
    },

    "studio_right": {
        "x": 502,
        "y": 127,
        "w": 717,
        "h": 481,
    },

    "bottom_bar": {
        "x": 0,
        "y": 609,
        "w": 1280,
        "h": 111,
    },
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
DETECTION_DESCRIPTION = "TWO-panel studio layout. The screen is split into exactly two boxes: a 449x481px left panel and a 717x481px right panel. The panels are taller than standard layouts. The right panel is larger and shows a graphic, video feed, or data display. Thin 122px header, 111px bottom bar, deep red background. NOT three panels."
