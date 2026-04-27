# H2V — Task Checklist

## Phase 1: Project Scaffold
- [x] Create directory structure (`templates/breaking_news_split/`, `core/`, `config/`, `output/`)
- [x] Add `__init__.py` files where needed for Python imports
- [x] Create `requirements.txt` with `pyyaml`

## Phase 2: Configuration Layer
- [x] Write `config/settings.yaml` — codec: libx264, CRF: 18, preset: fast, audio_codec: copy, output 1080×1920
- [x] Write `templates/breaking_news_split/config.py` — `TEMPLATE_CONFIG` dict with crop coordinates for headline, left panel, right panel
- [x] Verify crop coordinate estimates against a real frame (extract a frame with `ffmpeg -i input.mp4 -vframes 1 frame.png`)

## Phase 3: Core FFmpeg Runner
- [x] Write `core/ffmpeg_runner.py`
  - [x] Function that accepts a command as a list of args
  - [x] Use `subprocess.Popen` with `stdout=PIPE, stderr=PIPE`
  - [x] Stream stderr line-by-line to terminal in real-time (FFmpeg writes progress to stderr)
  - [x] Check return code on completion
  - [x] Raise `RuntimeError` with captured stderr on non-zero exit

## Phase 4: Template Transformer
- [x] Write `templates/breaking_news_split/transformer.py`
  - [x] Import `TEMPLATE_CONFIG` from sibling `config.py`
  - [x] Load `settings.yaml` using PyYAML
  - [x] Build `filter_complex` string programmatically:
    - [x] Three `crop` filters (headline, left, right) using config values
    - [x] Three `scale=1080:-2` filters
    - [x] `vstack=inputs=3` to stack all three
    - [x] `pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black` for final sizing
  - [x] Construct full FFmpeg arg list: `-i input -filter_complex "..." -map [out] -map 0:a -c:v codec -crf N -preset P -c:a copy output`
  - [x] Return the command as a list

## Phase 5: CLI Entry Point
- [x] Write `main.py` with argparse
  - [x] `--input` / `-i` — path to source video (required)
  - [x] `--output` / `-o` — output file path (optional, default: `output/<input_basename>_vertical.mp4`)
  - [x] `--template` / `-t` — template name (optional, default: `breaking_news_split`)
- [x] Load settings, resolve template module dynamically
- [x] Call transformer to get FFmpeg command
- [x] **Print the full command to terminal** (formatted for readability)
- [x] Call `core/ffmpeg_runner.py` to execute
- [x] Print success message with output path on completion

## Phase 6: Documentation
- [x] Write `README.md`
  - [x] Project description and purpose
  - [x] Prerequisites (Python 3.8+, FFmpeg on PATH)
  - [x] Installation (`pip install -r requirements.txt`)
  - [x] Usage examples
  - [x] How to tune crop coordinates
  - [x] How to add new templates

## Phase 7: Test & Tune
- [x] Run against a real India Today breaking news video
- [x] Extract a single frame from output to verify layout
- [x] Adjust crop coordinates in `config.py` if regions are misaligned
- [x] Verify audio passthrough works correctly
- [x] Test with different source videos to check coordinate stability
- [x] Confirm no encoding artifacts at CRF 18

## Phase 8: Polish (Optional / Post-MVP)
- [ ] Add FFmpeg availability check at startup with helpful error message
- [ ] Add `--dry-run` flag that prints the command without executing
- [ ] Add `--overwrite` flag to control whether existing output files are replaced
- [ ] Add progress bar parsing from FFmpeg stderr (frame count / duration)

---

**Total tasks: 30 (core) + 4 (optional polish)**
