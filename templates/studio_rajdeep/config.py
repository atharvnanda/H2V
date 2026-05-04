# ---------------------------------------------------------------------------
# Template: studio_rajdeep
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
# TODO: Fill in after reviewing the template's reference image.
DETECTION_DESCRIPTION = "TODO: brief visual description of this layout"
