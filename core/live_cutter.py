"""
core/live_cutter.py — Extracts clips from an ongoing YouTube livestream.

Uses sequence scraping to fetch segments from the YouTube livestream DVR buffer
and concatenates them into a single MP4 file.
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
    # Check system PATH
    system_path = shutil.which("yt-dlp")
    if system_path:
        return system_path
        
    # Check venv path
    proj_root = Path(__file__).parent.parent
    venv_path = proj_root / "venv" / "Scripts" / "yt-dlp.exe"
    if venv_path.exists():
        return str(venv_path)
        
    return "yt-dlp"

def download_segment(url: str, dest: Path) -> bool:
    """Downloads a single HLS segment chunk to dest."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"[live_cutter] Error downloading segment {url}: {e}")
        return False

def extract_livestream_clip(youtube_url: str, seconds_ago: float, duration: float, output_path: Path, progress_callback=None) -> None:
    """
    Extracts a clip of `duration` seconds starting `seconds_ago` seconds in the past
    from the YouTube livestream at `youtube_url` and saves it to `output_path`.
    """
    yt_dlp = get_yt_dlp_path()
    print(f"[live_cutter] Using yt-dlp path: {yt_dlp}")
    
    # 1. Fetch HLS media playlist URL using yt-dlp
    if progress_callback:
        progress_callback("Extracting livestream manifest...")
        
    cmd = [
        yt_dlp,
        "--extractor-args", "youtube:player-client=android,mweb",
        "-g",
        youtube_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimeError(f"Failed to extract livestream manifest. yt-dlp error: {err.stderr.strip()}")
        
    lines = result.stdout.strip().split('\n')
    if not lines or not lines[0].startswith("http"):
        raise RuntimeError("Failed to extract valid HLS playlist URL from livestream.")
        
    playlist_url = lines[0]
    print(f"[live_cutter] Fetched playlist URL: {playlist_url[:120]}...")
    
    # 2. Download media playlist and extract segment templates and current sequence number
    if progress_callback:
        progress_callback("Parsing livestream playlist...")
        
    resp = requests.get(playlist_url, timeout=15)
    resp.raise_for_status()
    
    manifest_lines = resp.text.split('\n')
    segment_urls = [line.strip() for line in manifest_lines if line.strip().startswith("http")]
    
    if not segment_urls:
        raise RuntimeError("No HLS segments found in the media playlist manifest.")
        
    # Extract base URL and found sequence
    base_seg_url = segment_urls[0]
    sq_match = re.search(r'/sq/(\d+)', base_seg_url)
    if not sq_match:
        raise RuntimeError("Could not find segment sequence identifier (/sq/) in the playlist URL.")
        
    found_sq = int(sq_match.group(1))
    
    # Extract sequence numbers from all segment URLs in the playlist to find the latest
    sequence_numbers = []
    for s_url in segment_urls:
        match = re.search(r'/sq/(\d+)', s_url)
        if match:
            sequence_numbers.append(int(match.group(1)))
            
    if not sequence_numbers:
        sequence_numbers = [found_sq]
        
    current_sq = max(sequence_numbers)
    print(f"[live_cutter] Parsed sequence ranges. Found base SQ: {found_sq}, latest current SQ: {current_sq}")
    
    # Calculate target sequence numbers
    # Each segment on YouTube is typically 5.0 seconds.
    segment_duration = 5.0
    segments_back = int(seconds_ago / segment_duration)
    num_segments = int(math.ceil(duration / segment_duration))
    
    target_start_sq = current_sq - segments_back
    target_end_sq = target_start_sq + num_segments - 1
    
    print(f"[live_cutter] target_start_sq: {target_start_sq}, target_end_sq: {target_end_sq} (num segments: {num_segments})")
    
    # 3. Download segments in parallel
    if progress_callback:
        progress_callback(f"Downloading {num_segments} chunks from stream archive...")
        
    temp_dir = Path(tempfile.mkdtemp(prefix="h2v_live_"))
    try:
        download_jobs = []
        for i in range(num_segments):
            sq = target_start_sq + i
            # Construct target URL by replacing /sq/{found_sq}/ with /sq/{sq}/
            target_url = base_seg_url.replace(f"/sq/{found_sq}/", f"/sq/{sq}/")
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
            # If we don't have any downloads at all, fail
            if successful_downloads == 0:
                raise RuntimeError("Failed to download any segments from the livestream DVR.")
                
        # 4. Concatenate segments using FFmpeg
        if progress_callback:
            progress_callback("Stitching and transcoding segments...")
            
        concat_list = temp_dir / "concat.txt"
        
        # Write files that actually exist (to handle missing segments gracefully if necessary)
        exist_chunks = []
        for i in range(num_segments):
            chunk_path = temp_dir / f"chunk_{i:04d}.ts"
            if chunk_path.exists():
                exist_chunks.append(chunk_path)
                
        concat_list.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in exist_chunks),
            encoding="utf-8"
        )
        
        # Transcode or copy. Copied ts segments to mp4 is usually fast, but transcoding cleans up timestamps.
        # Let's try to copy it first as it is super fast and standard.
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
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
