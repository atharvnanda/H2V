# H2V learnings

## [2026-05-21] YouTube Live Cut Feature Integration

### 1. Perceive & Understand
- **Goal**: Allow users to extract segments of an ongoing YouTube livestream by inputting URL, duration, and time ago. Review the extracted clip with a slider/trimmer, then crop it to 9:16 vertical format.
- **Challenge**: YouTube signed HLS playlists return a tiny, rolling duration (~30 seconds), preventing simple seek-based downloading. Modifying or expanding the signature is blocked with HTTP 403.
- **Solution**: Use `yt-dlp` with `android,mweb` user-client args to extract the master media playlist URL. Access older segments within the 12-hour DVR buffer by parsing the base segment sequence URL and fetching target sequence IDs directly.

### 2. Reason & Plan
- Implemented `core/live_cutter.py` to concurrently fetch segment TS files and concatenate them with FFmpeg.
- Added API endpoints in `app.py` for `/live-cut`, `/live-cut/status`, `/live-cut/download`, and `/process-vertical`.
- Updated `frontend/index.html` with a tabbed UI, duration inputs, and a custom range slider for interactive trimming.

### 3. Act & Implement
- Wrote code in small, atomic blocks.
- Solved Windows default console Unicode crashes by replacing non-ASCII characters (`…`, `—`) in status strings.
- Re-run Uvicorn server whenever code imports/cache changed.

### 4. Refine & Reflect
- Integration testing verified both livestream clip scraping and downstream H2V vertical conversion.
- Verified that output resolution and aspect ratios are preserved and successfully formatted.
