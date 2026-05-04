# ---------------------------------------------------------------------------

# Template: 2panel_unequal_studio
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
        "h": 120,
    },

    "studio_left": {
        "x": 45,
        "y": 123,
        "w": 478,
        "h": 397,
    },

    "studio_right": {
        "x": 526,
        "y": 123,
        "w": 711,
        "h": 397,
    },

    "bottom_bar": {
        "x": 0,
        "y": 521,
        "w": 1280,
        "h": 199,
    },
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
DETECTION_DESCRIPTION = "TWO-panel studio layout. The screen is split into exactly two boxes: a 478x397px left panel and a 711x397px right panel. The left panel can show one anchor or multiple guests stacked. The right panel is larger and shows a graphic, video feed, or data display. Thin 120px header, 199px bottom bar, deep red background. NOT three panels."
