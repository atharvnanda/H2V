# ---------------------------------------------------------------------------
# Template: studio_3_panels
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
        "x": 42,
        "y": 126,
        "w": 395,
        "h": 400,
    },

    "studio_mid": {
        "x": 443,
        "y": 126,
        "w": 395,
        "h": 400,
    },

    "studio_right": {
        "x": 843,
        "y": 126,
        "w": 395,
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
DETECTION_DESCRIPTION = "THREE-panel studio layout with three EQUAL-width 395x400px panels side-by-side. All three panels are the same width showing anchors/guests. Thin 122px dark/gold header (e.g. 'INDIAN POLITICAL LEAGUE'), 196px bottom bar. Panels are TALL (400px). NOT narrow-wide-narrow like middlesplit. NOT short 270px panels like breaking_news."
