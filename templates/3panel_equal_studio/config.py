# ---------------------------------------------------------------------------
# Template: 3panel_equal_studio
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
DETECTION_DESCRIPTION = "THREE EQUAL-width panels (1:1:1 ratio). Each panel is 395x400px — all the SAME width. Shows anchors/guests with room in each panel. Thin 122px dark/gold header, 196px bottom bar. Panels are TALL (400px). All three panels have EQUAL width — none is wider or narrower than the others."
