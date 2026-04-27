# ---------------------------------------------------------------------------
# Template: breaking_news_split
# ---------------------------------------------------------------------------
# All pixel values are for a 1920×1080 source frame.
# Adjust these numbers to align with your specific broadcast layout.
#
# How to find the right values:
#   1. Extract a frame:   ffmpeg -i input.mp4 -vframes 1 frame.png
#   2. Open frame.png in any image editor (Paint, GIMP, Photoshop).
#   3. Note the y-coordinate where the headline bar ends and panels begin.
#   4. Note the y-coordinate where the panels end (before player chrome).
#   5. Update the values below accordingly.
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
        "x": 0,
        "y": 250,           # must match headline.h
        "w": 638,
        "h": 270,           # ← tune this: panel height (520 - 250)
    },

    # ── Region 3: Right panel (event / b-roll) ────────────────────────────────
    "right_panel": {
        "x": 638,           # must match left_panel.w
        "y": 250,           # must match headline.h
        "w": 642,           # 1280 - 638
        "h": 270,           # must match left_panel.h
    },
}
