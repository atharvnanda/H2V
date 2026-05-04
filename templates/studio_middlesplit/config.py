# ---------------------------------------------------------------------------
# Template: studio_middlesplit
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
        "w": 233,
        "h": 400,
    },

    "mid_video": {
        "x": 280,
        "y": 123,
        "w": 711,
        "h": 400,
    },

    "studio_right": {
        "x": 994,
        "y": 123,
        "w": 242,
        "h": 400,
    },

    "bottom_bar": {
        "x": 0,
        "y": 524,
        "w": 1280,
        "h": 196,
    },
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
DETECTION_DESCRIPTION = "THREE-panel studio layout with a narrow-WIDE-narrow split. A large 711x400px center video panel is flanked by two very narrow side panels (left: 233x400px, right: 242x400px) showing individual anchors/reporters. Thin 120px header, 196px bottom bar. The side panels are much narrower than the center."
