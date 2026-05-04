# ---------------------------------------------------------------------------
# Template: fullscreen_breaking
# ---------------------------------------------------------------------------
# A simple template that takes the entire 16:9 frame, scales it to fit the 
# 1080 width, and adds padding to the top and bottom to make it 1080x1920.
# ---------------------------------------------------------------------------

TEMPLATE_CONFIG: dict = {
    "source_width": 1280,
    "source_height": 720,
}

# ── Auto-detection hint (used by core/classifier.py) ──────────────────────────
# TODO: Fill in after reviewing the template's reference image.
DETECTION_DESCRIPTION = "TODO: brief visual description of this layout"
