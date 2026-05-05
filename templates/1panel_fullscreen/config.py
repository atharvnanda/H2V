# ---------------------------------------------------------------------------
# Template: 1panel_fullscreen
# ---------------------------------------------------------------------------
# A simple template that takes the entire 16:9 frame, scales it to fit the 
# 1080 width, and adds padding to the top and bottom to make it 1080x1920.
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
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
DETECTION_DESCRIPTION = "Fullscreen 1280x720px layout with no panel splits. Typically shows a single person or scene with 'Breaking News' graphics overlaid on the main frame."
