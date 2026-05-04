# ---------------------------------------------------------------------------
# Template: 3panel_wide_center
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
DETECTION_DESCRIPTION = "THREE UNEQUAL-width panels (1:3:1 ratio). The CENTER panel is MUCH WIDER (711x400px) than the two NARROW side panels (left: 233x400px, right: 242x400px). Side panels are barely wide enough for a single person's face. Thin 120px header, 196px bottom bar. The center panel is roughly 3x wider than each side panel."
