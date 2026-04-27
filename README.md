# H2V — Horizontal-to-Vertical News Video Reformatter

Converts a 16:9 (1920×1080) Indian news broadcast video into a 9:16 (1080×1920) vertical
video by cropping and stacking the headline bar, left panel, and right panel using FFmpeg.

## Prerequisites

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) installed and on your `PATH`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Minimal — output saved to output/<input_stem>_vertical.mp4
python main.py --input path/to/video.mp4

# Full options
python main.py -i video.mp4 -o custom_output.mp4 --template breaking_news_split
```

The tool will print the full FFmpeg command before executing it so you can
inspect or copy-paste it for manual debugging.

## Tuning Crop Coordinates

Each template's crop region is defined in a plain dictionary inside
`templates/<template_name>/config.py`.  No logic lives there — only pixel values.

**Step 1:** Extract a frame from your source video:
```bash
ffmpeg -i input.mp4 -vframes 1 frame.png
```

**Step 2:** Open `frame.png` in any image editor and note:
- The y-coordinate where the headline bar ends (→ `headline.h`, `left_panel.y`, `right_panel.y`)
- The y-coordinate where the panels end before player controls (→ `left_panel.h`, `right_panel.h`)
- The x-coordinate where the two panels split (→ `left_panel.w`, `right_panel.x`)

**Step 3:** Update the values in `templates/breaking_news_split/config.py`.

## Adding a New Template

1. Create a new folder: `templates/<your_template>/`
2. Add `__init__.py`, `config.py` (with a `TEMPLATE_CONFIG` dict), and `transformer.py`
   (with a `build_command(input_path, output_path) -> list[str]` function).
3. Use it: `python main.py -i video.mp4 --template <your_template>`

No changes to `main.py` or `core/` are required.

## Project Structure

```
h2v/
├── main.py                            # CLI entry point (argparse)
├── templates/
│   └── breaking_news_split/
│       ├── config.py                  # Crop coordinates — tune these
│       └── transformer.py            # Builds FFmpeg filter_complex from config
├── core/
│   └── ffmpeg_runner.py              # Subprocess wrapper with live streaming
├── config/
│   └── settings.yaml                 # Codec, CRF, preset, output resolution
├── output/                           # Default output directory
├── requirements.txt
└── README.md
```

## Global Settings (`config/settings.yaml`)

| Key          | Default     | Description                                 |
|--------------|-------------|---------------------------------------------|
| `width`      | 1080        | Output video width (px)                     |
| `height`     | 1920        | Output video height (px)                    |
| `codec`      | libx264     | FFmpeg video codec                          |
| `crf`        | 18          | Constant Rate Factor (lower = better quality)|
| `preset`     | fast        | Encoding speed/compression tradeoff         |
| `audio_codec`| copy        | Audio passthrough (no re-encoding)          |
| `pad_color`  | 0xAA0000    | Padding color (news-red) for height gaps    |
