# ---------------------------------------------------------------------------
# Template: breaking_news_3_panels
# ---------------------------------------------------------------------------
# All pixel values are for a 1280×720 source frame.
# Adjust these numbers to align with your specific broadcast layout.
#
# How to find the right values:
#   1. Extract a frame:   ffmpeg -i input.mp4 -vframes 1 frame.png
#   2. Open frame.png in any image editor (Paint, GIMP, Photoshop).
#   3. Note the y-coordinate where the headline bar ends and panels begin.
#   4. Note the y-coordinate where the panels end.
#   5. Note the x-coordinates where the three panels split.
#   6. Update the values below accordingly.
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
        "h": 250,
    },

    # ── Region 2: Left panel ──────────────────────────────────────────────────
    "left_panel": {
        "x": 45,
        "y": 250,
        "w": 395,
        "h": 270,
    },

    # ── Region 3: Mid panel ───────────────────────────────────────────────────
    "mid_panel": {
        "x": 441,
        "y": 250,
        "w": 395,
        "h": 270,
    },

    # ── Region 4: Right panel ─────────────────────────────────────────────────
    "right_panel": {
        "x": 838,
        "y": 250,
        "w": 395,
        "h": 270,
    },

    # ── Region 5: Bottom animation/background ─────────────────────────────────
    "bottom_bar": {
        "x": 0,
        "y": 521,
        "w": 1280,
        "h": 199,           # 720 - 521
    },
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
# TODO: Fill in after reviewing the template's reference image.
DETECTION_DESCRIPTION = "TODO: brief visual description of this layout"
