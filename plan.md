# H2V — Horizontal-to-Vertical News Video Reformatter

## 1. What This Project Does

A Python CLI tool that takes a standard 16:9 (1920×1080) Indian news channel video — with a headline bar on top and two side-by-side anchor/event panels below — and converts it into a 9:16 vertical video (1080×1920) suitable for YouTube Shorts, Instagram Reels, etc.

The tool uses **FFmpeg's `filter_complex`** to crop, scale, and vertically stack three regions from the source frame into a single tall output frame.

---

## 2. Source Video Anatomy (1920×1080)

Based on the reference frame analysis:

```
┌──────────────────────────────────────┐  y=0
│          BREAKING NEWS               │  ← Red banner + headline text
│  BJP UPS THE ANTE AGAINST AAP ...    │
├──────────────────┬───────────────────┤  y≈290  (headline/panel boundary)
│                  │                   │
│   LEFT PANEL     │   RIGHT PANEL     │
│   (Anchor)       │   (Event/B-roll)  │
│                  │                   │
├──────────────────┴───────────────────┤  y≈980  (above player controls)
│  [player controls / bottom bar]      │
└──────────────────────────────────────┘  y=1080
```

### Estimated Crop Regions (to be tuned per-template)

| Region       | x    | y    | width | height | Notes                                    |
|--------------|------|------|-------|--------|------------------------------------------|
| Headline Bar | 0    | 0    | 1920  | ~290   | Full-width red banner + headline text    |
| Left Panel   | 0    | ~290 | ~960  | ~690   | Left half, below headline, above controls|
| Right Panel  | ~960 | ~290 | ~960  | ~690   | Right half, mirrors left panel bounds    |

> **These values live in `config.py` as a plain dictionary and are the primary tuning knobs.**

---

## 3. Output Video Layout (1080×1920)

Each cropped region is **scaled to 1080px wide** (maintaining aspect ratio within the scale), then stacked vertically:

```
┌────────────┐
│  HEADLINE  │  ← scaled from 1920→1080 wide, height proportional (~163px)
├────────────┤
│            │
│ LEFT PANEL │  ← scaled from 960→1080 wide, height proportional (~777px)
│            │
├────────────┤
│            │
│RIGHT PANEL │  ← scaled from 960→1080 wide, height proportional (~777px)
│            │
└────────────┘
   Total height ≈ 163 + 777 + 777 = ~1717px
   (pad to 1920 or adjust crops to fill exactly)
```

### Height Budget Problem

1080×1920 gives us 1920px of vertical space. The three panels at native proportions may not sum to exactly 1920. Strategy:

- **Option A**: Pad remaining space with black bars (simple, safe).
- **Option B**: Slightly stretch/crop panels to fill exactly 1920 (better visual, minor distortion).
- **Option C**: Add a solid-color or branded spacer bar between sections.

> **Decision:** Default to **Option A** (pad with black). User can override via config later.

---

## 4. FFmpeg Filter Chain Design

The `filter_complex` string will be built **programmatically** from the config dictionary. No hardcoded pixel values in the FFmpeg command.

### Pseudocode for the filter chain:

```
[0:v] crop=w_h:h_h:x_h:y_h, scale=1080:-2 [headline];
[0:v] crop=w_l:h_l:x_l:y_l, scale=1080:-2 [left];
[0:v] crop=w_r:h_r:x_r:y_r, scale=1080:-2 [right];
[headline][left][right] vstack=inputs=3 [stacked];
[stacked] pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black [out]
```

- `crop` extracts each region using coordinates from config
- `scale=1080:-2` scales width to 1080 and auto-calculates height (divisible by 2 for h264)
- `vstack=inputs=3` stacks the three streams vertically
- `pad` ensures final output is exactly 1080×1920 (centered, black fill)

---

## 5. Project Structure

```
h2v/
├── main.py                           # CLI entry point (argparse)
├── templates/
│   └── breaking_news_split/
│       ├── config.py                 # Crop coordinates dict + output dims
│       └── transformer.py           # Builds filter_complex string from config
├── core/
│   └── ffmpeg_runner.py              # Generic: runs any ffmpeg command via subprocess
├── config/
│   └── settings.yaml                 # Codec, CRF, preset, resolution defaults
├── output/                           # Default output directory
├── requirements.txt                  # pyyaml (only external dep)
└── README.md
```

### Why this structure over the proposed one

- Renamed `transformer/ffmpeg_builder.py` → `core/ffmpeg_runner.py` — clearer naming; this module **runs** commands, it doesn't build filter chains (that's the template's job).
- Everything else stays as proposed.

---

## 6. Module Responsibilities

### `main.py`
- Parse CLI args: `--input` (required), `--output` (optional, defaults to `output/`), `--template` (default: `breaking_news_split`)
- Load `settings.yaml`
- Delegate to the selected template's `transformer.py` to build the FFmpeg command
- **Print the full FFmpeg command** to terminal before execution (for debug/verification)
- Call `core/ffmpeg_runner.py` to execute
- Stream stdout/stderr live; raise clear error on non-zero exit

### `templates/breaking_news_split/config.py`
- Export a single `TEMPLATE_CONFIG` dictionary:
  ```python
  TEMPLATE_CONFIG = {
      "headline": {"x": 0, "y": 0, "w": 1920, "h": 290},
      "left_panel": {"x": 0, "y": 290, "w": 960, "h": 690},
      "right_panel": {"x": 960, "y": 290, "w": 960, "h": 690},
      "output_width": 1080,
      "output_height": 1920,
  }
  ```
- All pixel values in one place — easy to tune without touching logic

### `templates/breaking_news_split/transformer.py`
- Read `TEMPLATE_CONFIG` from `config.py`
- Read global settings from `settings.yaml` (codec, CRF, preset)
- Build the `filter_complex` string programmatically using f-strings/templates
- Return the complete `ffmpeg` command as a list of args

### `core/ffmpeg_runner.py`
- Accept a command (list of args)
- Execute via `subprocess.Popen`
- Stream stdout/stderr line-by-line to terminal in real-time
- Check return code; raise `RuntimeError` with stderr on failure

### `config/settings.yaml`
```yaml
output:
  width: 1080
  height: 1920
  codec: libx264
  crf: 18
  audio_codec: copy
  preset: fast
```

---

## 7. How It Will Be Built

1. **Scaffold the project structure** — create all directories and empty files
2. **Write `settings.yaml`** — global encoding defaults
3. **Write `config.py`** — the crop coordinate dictionary (estimated from image, will need tuning)
4. **Write `core/ffmpeg_runner.py`** — subprocess wrapper with live streaming + error handling
5. **Write `templates/breaking_news_split/transformer.py`** — filter chain builder
6. **Write `main.py`** — CLI with argparse, wiring everything together
7. **Write `requirements.txt`** — just `pyyaml`
8. **Write `README.md`** — usage docs
9. **Test with a real video** — tune crop coordinates based on actual output

---

## 8. Resolved Questions

1. **Crop coordinates** — Only this template for now; coordinates are fixed in config.
2. **Bottom bar** — Ignore player controls; crop only the pure video frame area.
3. **Channel logo** — Acceptable to include in headline crop.
4. **Height gap** — Pad with the news-red color (`0xAA0000`) instead of black.
5. **Multiple templates** — Extensibility is desired; dynamic template loading via `--template` flag.
6. **Audio** — No processing; `audio_codec: copy` passthrough only.
7. **FFmpeg check** — Not required.
