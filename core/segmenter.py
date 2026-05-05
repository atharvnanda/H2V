"""core/segmenter.py — Smart template segmentation using geometry scoring."""
from __future__ import annotations

import cv2
import numpy as np

# ── Tuneable constants ────────────────────────────────────────────────────────
SAMPLE_FPS = 2                  # 2 fps catches short transitions
MIN_TEMPLATE_SCORE = 80         # Below this, frame is considered a transition/garbage


def extract_frames(
    video_path: str, fps: int = SAMPLE_FPS,
) -> list[tuple[float, np.ndarray]]:
    """Return [(timestamp_sec, frame), ...] sampled at *fps*."""
    cap = cv2.VideoCapture(video_path)
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    interval = max(1, int(native_fps / fps))
    frames: list[tuple[float, np.ndarray]] = []
    idx = 0
    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))
        frames.append((idx / native_fps, frame))
        idx += interval
    cap.release()
    return frames


def build_segments(video_path: str) -> list[dict]:
    """Sample frames, score them via geometry, and group into segments."""
    from core.geometry import rank_templates

    print(f"[segmenter] Sampling frames at {SAMPLE_FPS}fps...")
    frames = extract_frames(video_path)
    if not frames:
        raise RuntimeError("No frames extracted from video.")

    duration = frames[-1][0]
    
    # 1. Score every frame (Geometry only, no LLM)
    raw_labels: list[str] = []
    for ts, frame in frames:
        ranked = rank_templates(frame=frame)
        if not ranked or ranked[0][1] < MIN_TEMPLATE_SCORE:
            raw_labels.append("TRANSITION")
        else:
            raw_labels.append(ranked[0][0])  # Top geometry guess

    # 2. Debounce labels (require stability) to prevent flickers
    smooth_labels = list(raw_labels)
    if raw_labels:
        STABLE_FRAMES = 3  # Need 3 consecutive identical frames (1.5s at 2fps) to switch
        current_stable = raw_labels[0]
        streak = 1
        
        for i in range(1, len(raw_labels)):
            if raw_labels[i] == raw_labels[i-1]:
                streak += 1
            else:
                streak = 1
                
            if streak == STABLE_FRAMES:
                current_stable = raw_labels[i]
                # Backdate the previous frames in the streak to the new stable layout
                # This removes the 1.5s delay while still enforcing stability
                for j in range(STABLE_FRAMES):
                    smooth_labels[i - j] = current_stable
            elif streak > STABLE_FRAMES:
                smooth_labels[i] = current_stable
            else:
                smooth_labels[i] = current_stable

    # 3. Group into segments
    segments: list[dict] = []
    current_label = smooth_labels[0]
    start_ts = 0.0

    for i in range(1, len(smooth_labels)):
        if smooth_labels[i] != current_label:
            end_ts = frames[i][0]
            # Add segment
            seg_type = "TRANSITION" if current_label == "TRANSITION" else "TEMPLATE"
            segments.append({
                "type": seg_type,
                "start": start_ts,
                "end": end_ts,
                "geom_guess": current_label if seg_type == "TEMPLATE" else None
            })
            current_label = smooth_labels[i]
            start_ts = end_ts

    # Add final segment
    seg_type = "TRANSITION" if current_label == "TRANSITION" else "TEMPLATE"
    segments.append({
        "type": seg_type,
        "start": start_ts,
        "end": duration,
        "geom_guess": current_label if seg_type == "TEMPLATE" else None
    })

    return segments


def classify_segments(segments: list[dict], video_path: str) -> list[dict]:
    """For each TEMPLATE segment, extract midpoint and run full classify()."""
    from core.classifier import classify

    cap = cv2.VideoCapture(video_path)
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25

    for seg in segments:
        if seg["type"] != "TEMPLATE":
            continue

        mid_ts = (seg["start"] + seg["end"]) / 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(mid_ts * native_fps))
        ok, frame = cap.read()
        if not ok:
            seg["template"] = seg["geom_guess"]
            continue
        
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # Full classification (Geometry + LLM Tiebreaker if needed)
        try:
            seg["template"] = classify(frame=frame)
        except Exception:
            seg["template"] = seg["geom_guess"]

    cap.release()
    return segments


def segment_video(video_path: str) -> list[dict]:
    """Full pipeline."""
    segments = build_segments(video_path)
    
    print(f"[segmenter] Found {len(segments)} segment(s). Classifying midpoints...")
    segments = classify_segments(segments, video_path)

    for seg in segments:
        label = seg.get("template") or seg.get("geom_guess") or "—"
        print(f"  {seg['type']:12s}  {seg['start']:6.1f}s – {seg['end']:6.1f}s  → {label}")

    return segments
