# Template Auto-Detection Plan

**Goal:** Make `--template` optional by auto-detecting the layout from a video frame using Groq's vision LLM.

---

## 1. `core/prompts/classify.txt`

```text
You are a broadcast news layout classifier.

Given a single video frame, identify which template best matches the visual layout.

{template_descriptions}

Reply with ONLY the exact template folder name. No explanation, no punctuation.
```

- Single placeholder `{template_descriptions}` gets filled at runtime.
- Forces the model to output a raw folder name for easy validation.

---

## 2. `core/classifier.py`

```python
"""Auto-detect template from a video frame using Groq vision API."""
from __future__ import annotations

import base64, importlib, subprocess, tempfile
from pathlib import Path

from groq import Groq

PROMPT_PATH = Path(__file__).parent / "prompts" / "classify.txt"
TEMPLATES_DIR = Path(__file__).parents[1] / "templates"


def _extract_frame(video_path: str) -> bytes:
    """Extract a single frame (1 sec in) as JPEG bytes via FFmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1", "-i", video_path,
         "-frames:v", "1", "-q:v", "2", tmp_path],
        capture_output=True, check=True,
    )
    return Path(tmp_path).read_bytes()


def _get_template_descriptions() -> dict[str, str]:
    """Load DETECTION_DESCRIPTION from each template's config.py."""
    descriptions = {}
    for folder in TEMPLATES_DIR.iterdir():
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"templates.{folder.name}.config")
            desc = getattr(mod, "DETECTION_DESCRIPTION", None)
            if desc:
                descriptions[folder.name] = desc
        except Exception:
            continue
    return descriptions


def classify(video_path: str) -> str:
    """Return the detected template folder name."""
    descs = _get_template_descriptions()
    if not descs:
        raise RuntimeError("No templates have DETECTION_DESCRIPTION defined.")

    # Build prompt
    block = "\n".join(f"- {name}: {desc}" for name, desc in descs.items())
    prompt = PROMPT_PATH.read_text().replace("{template_descriptions}", block)

    # Encode frame
    frame = _extract_frame(video_path)
    b64 = base64.b64encode(frame).decode()

    # Call Groq
    client = Groq()  # uses GROQ_API_KEY env var
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=32,
    )

    result = resp.choices[0].message.content.strip()

    # Validate
    if result not in descs:
        raise ValueError(
            f"Model returned '{result}', expected one of: {list(descs.keys())}"
        )
    return result
```

**Key decisions:**
- Frame extracted at `t=1s` (avoids black leader frames).
- `GROQ_API_KEY` from env (standard Groq SDK behaviour).
- Hard validation: result must match a known folder name exactly.

---

## 3. Add `DETECTION_DESCRIPTION` to each `templates/<name>/config.py`

Append a single string constant to the **end** of each file. Existing code untouched.

| Template | `DETECTION_DESCRIPTION` |
|---|---|
| `breaking_news_2_panels` | `"Breaking-news banner at top, two equal side-by-side panels in the middle, ticker/animation bar at bottom."` |
| `breaking_news_3_panels` | `"Breaking-news banner at top, three equal side-by-side panels in the middle, ticker/animation bar at bottom."` |
| `fullscreen_breaking` | `"Single fullscreen 16:9 frame with no panel splits; breaking-news graphics overlaid."` |
| `studio_3_panels` | `"Thin headline strip at top, three equal studio panels in the middle, ticker bar at bottom."` |
| `studio_middlesplit` | `"Thin headline strip at top, narrow person panels on left and right flanking a wide centre video, ticker bar at bottom."` |
| `studio_rajdeep` | `"Thin headline strip at top, two unequal studio panels (left narrower, right wider), ticker bar at bottom."` |

---

## 4. Edit `main.py`

Minimal diff — make `--template` default to `None` and add a detection branch:

```diff
     parser.add_argument(
         "-t", "--template",
-        default="breaking_news_2_panels",
+        default=None,
         metavar="TEMPLATE",
         help=(
-            "Template name to use for layout (must match a folder under templates/). "
-            "Default: breaking_news_2_panels"
+            "Template name (folder under templates/). "
+            "Auto-detected from video if omitted."
         ),
     )
```

In `main()`, after resolving `input_path`:

```diff
+    # ── Auto-detect template if not provided ──────────────────────────────
+    if args.template is None:
+        from core.classifier import classify
+        args.template = classify(str(input_path))
+        print(f"[h2v] Auto-detected template: {args.template}")
+
     transformer = load_transformer(args.template)
```

---

## File Checklist

| # | Action | File |
|---|--------|------|
| 1 | **Create** | `core/prompts/classify.txt` |
| 2 | **Create** | `core/classifier.py` |
| 3 | **Append** | `templates/breaking_news_2_panels/config.py` |
| 4 | **Append** | `templates/breaking_news_3_panels/config.py` |
| 5 | **Append** | `templates/fullscreen_breaking/config.py` |
| 6 | **Append** | `templates/studio_3_panels/config.py` |
| 7 | **Append** | `templates/studio_middlesplit/config.py` |
| 8 | **Append** | `templates/studio_rajdeep/config.py` |
| 9 | **Edit** | `main.py` (two small diffs) |
| 10 | **Add dep** | `requirements.txt` → add `groq` |

---

## New Dependency

```
groq
```

Add to `requirements.txt`. No other new deps — `base64`, `subprocess`, `tempfile` are stdlib.
