"""
core/live_cutter.py — Extracts clips from an ongoing YouTube livestream.

Uses yt-dlp to fetch the full HLS DVR playlist (which covers ~4 hours of buffer),
then downloads the exact segments needed using the properly-signed URLs from the
playlist itself. This avoids the 404 errors caused by URL forging across CDN hosts.
"""
from __future__ import annotations

import re
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests

from core import ffmpeg_runner

def get_yt_dlp_path() -> str:
    """Find the path to the yt-dlp executable, favoring virtual environment."""
    # Check venv path first
    proj_root = Path(__file__).parent.parent
    venv_path = proj_root / "venv" / "Scripts" / "yt-dlp.exe"
    if venv_path.exists():
        return str(venv_path)
        
    # Fallback to system PATH
    system_path = shutil.which("yt-dlp")
    if system_path:
        return system_path
        
    return "yt-dlp"

def download_segment(url: str, dest: Path) -> bool:
    """Downloads a single segment chunk to dest."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"[live_cutter] Error downloading segment: {e}")
        return False

def _get_full_playlist(yt_dlp: str, youtube_url: str, itag: str = "96") -> tuple[list[str], list[int], float]:
    """
    Use yt-dlp to get the JSON metadata, extract the per-quality HLS playlist URL,
    then fetch the full playlist to get all segment URLs with valid signatures.
    
    Returns:
        segment_urls: list of full segment URLs from the playlist
        sequence_numbers: list of corresponding sequence numbers
        segment_duration: duration of each segment in seconds
    """
    import json

    # Step 1: Get format info via yt-dlp JSON dump
    cmd = [yt_dlp, "--dump-json", "--skip-download", youtube_url]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to extract stream info: {result.stderr.strip()[:500]}")
    
    data = json.loads(result.stdout)
    formats = data.get("formats", [])
    
    # Find the target format (try 1080p first, then 720p, then best available)
    target_format = None
    for preferred_itag in [itag, "96", "95", "94", "93"]:
        for f in formats:
            if f.get("format_id") == preferred_itag:
                target_format = f
                break
        if target_format:
            break
    
    if not target_format and formats:
        # Fallback: use the last (highest quality) format
        target_format = formats[-1]
    
    if not target_format:
        raise RuntimeError("No video formats found for this livestream.")
    
    playlist_url = target_format["url"]
    print(f"[live_cutter] Using format: itag={target_format['format_id']} "
          f"resolution={target_format.get('resolution', 'unknown')}")
    
    # Step 2: Fetch the full HLS media playlist
    resp = requests.get(playlist_url, timeout=15)
    resp.raise_for_status()
    
    manifest_lines = resp.text.strip().split('\n')
    segment_urls = [line.strip() for line in manifest_lines if line.strip().startswith("http")]
    
    if not segment_urls:
        raise RuntimeError("No segment URLs found in the HLS playlist.")
    
    # Extract segment duration from #EXTINF tags
    segment_duration = 5.0
    for line in manifest_lines:
        if line.startswith("#EXTINF:"):
            match = re.search(r'#EXTINF:([\d\.]+)', line)
            if match:
                segment_duration = float(match.group(1))
                break
    
    # Extract sequence numbers
    sequence_numbers = []
    for s_url in segment_urls:
        match = re.search(r'/sq/(\d+)', s_url)
        if match:
            sequence_numbers.append(int(match.group(1)))
        else:
            sequence_numbers.append(-1)
    
    # Filter out any URLs without valid sequence numbers
    valid_pairs = [(url, sq) for url, sq in zip(segment_urls, sequence_numbers) if sq >= 0]
    if not valid_pairs:
        raise RuntimeError("Could not parse sequence numbers from segment URLs.")
    
    segment_urls, sequence_numbers = zip(*valid_pairs)
    
    print(f"[live_cutter] Playlist has {len(segment_urls)} segments, "
          f"sq range: {min(sequence_numbers)}-{max(sequence_numbers)}, "
          f"segment duration: {segment_duration}s, "
          f"DVR coverage: ~{len(segment_urls) * segment_duration / 3600:.1f} hours")
    
    return list(segment_urls), list(sequence_numbers), segment_duration


def extract_livestream_clip(youtube_url: str, seconds_ago: float, duration: float, output_path: Path, progress_callback=None) -> None:
    """
    Extracts a clip of `duration` seconds starting `seconds_ago` seconds in the past
    from the YouTube livestream at `youtube_url` and saves it to `output_path`.
    """
    yt_dlp = get_yt_dlp_path()
    print(f"[live_cutter] Using yt-dlp path: {yt_dlp}")
    
    # 1. Fetch the full HLS playlist with all signed segment URLs
    if progress_callback:
        progress_callback("Fetching livestream playlist...")
        
    segment_urls, sequence_numbers, segment_duration = _get_full_playlist(yt_dlp, youtube_url)
    
    # Build a lookup: sequence_number -> URL
    sq_to_url = dict(zip(sequence_numbers, segment_urls))
    
    current_sq = max(sequence_numbers)
    min_sq = min(sequence_numbers)
    
    # 2. Calculate which segments we need
    if progress_callback:
        progress_callback("Calculating target segments...")
    
    # The latest segment in the playlist is the "live edge".
    # seconds_ago tells us how far back from that edge we want to go.
    # Each segment is `segment_duration` seconds long.
    # Segment current_sq covers [0, segment_duration) seconds ago.
    # Segment current_sq - 1 covers [segment_duration, 2*segment_duration) seconds ago.
    # So the segment containing our start point is:
    #   current_sq - floor(seconds_ago / segment_duration)
    
    segments_back = int(math.floor(seconds_ago / segment_duration))
    target_start_sq = current_sq - segments_back
    
    # The trim offset is how far into the first segment our clip actually starts
    trim_start = seconds_ago - (segments_back * segment_duration)
    # Since the segment starts at (segments_back * seg_dur) seconds ago,
    # and we want to start at seconds_ago, the offset into the segment is:
    # segment_duration - trim_start  (because time flows forward within a segment)
    trim_offset = segment_duration - trim_start
    if trim_offset >= segment_duration:
        trim_offset = 0.0
    
    # How many segments do we need to cover trim_offset + duration?
    total_time_needed = trim_offset + duration
    num_segments = int(math.ceil(total_time_needed / segment_duration))
    
    # Ensure we don't go below the minimum available sequence
    if target_start_sq < min_sq:
        print(f"[live_cutter] WARNING: Requested segment sq/{target_start_sq} is before "
              f"the earliest available sq/{min_sq}. Clamping to earliest available.")
        target_start_sq = min_sq
    
    target_end_sq = target_start_sq + num_segments - 1
    
    print(f"[live_cutter] seconds_ago={seconds_ago:.1f}, duration={duration:.1f}")
    print(f"[live_cutter] target_start_sq={target_start_sq}, num_segments={num_segments}, "
          f"trim_offset={trim_offset:.3f}s")
    
    # 3. Collect segment URLs — use directly from playlist when available, forge when not
    if progress_callback:
        progress_callback(f"Downloading {num_segments} chunks from stream archive...")
        
    temp_dir = Path(tempfile.mkdtemp(prefix="h2v_live_"))
    try:
        download_jobs = []
        # Use the first segment URL in the playlist as the forge template
        # (its CDN host + signature covers the full DVR range)
        forge_template_url = segment_urls[0]
        forge_template_sq = sequence_numbers[0]
        
        for i in range(num_segments):
            sq = target_start_sq + i
            
            if sq in sq_to_url:
                # Use the exact URL from the playlist (guaranteed valid signature)
                target_url = sq_to_url[sq]
            else:
                # Forge using the FIRST segment's URL template
                # (its CDN host accepts the full DVR range)
                target_url = forge_template_url.replace(
                    f"/sq/{forge_template_sq}/", f"/sq/{sq}/"
                )
                print(f"[live_cutter] Segment sq/{sq} not in playlist, forging URL from template")
            
            dest_file = temp_dir / f"chunk_{i:04d}.ts"
            download_jobs.append((target_url, dest_file))
            
        # Run downloads concurrently
        successful_downloads = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(download_segment, url, path) for url, path in download_jobs]
            for idx, future in enumerate(futures):
                if future.result():
                    successful_downloads += 1
                if progress_callback:
                    progress_callback(f"Downloading chunks: {successful_downloads}/{num_segments} complete...")
                    
        if successful_downloads < num_segments:
            print(f"[live_cutter] Warning: {num_segments - successful_downloads} segment downloads failed!")
            if successful_downloads == 0:
                raise RuntimeError("Failed to download any segments from the livestream DVR.")
                
        # 4. Concatenate segments and trim using FFmpeg
        if progress_callback:
            progress_callback("Stitching and transcoding segments...")
            
        concat_list = temp_dir / "concat.txt"
        
        exist_chunks = []
        for i in range(num_segments):
            chunk_path = temp_dir / f"chunk_{i:04d}.ts"
            if chunk_path.exists():
                exist_chunks.append(chunk_path)
                
        concat_list.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in exist_chunks),
            encoding="utf-8"
        )
        
        # Transcode with precise trim: -ss skips into the concatenated result,
        # -t limits the output to exactly the requested duration.
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-ss", f"{trim_offset:.3f}",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "superfast",
            "-c:a", "aac",
            str(output_path)
        ]
        
        ffmpeg_runner.run(cmd)
        print(f"[live_cutter] Successfully created clip at {output_path}")
        
    finally:
        # Cleanup temporary files
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
