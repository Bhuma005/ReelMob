"""
smart_reframe.py

A production-ready "Smart Reframe" module to convert video aspect ratios.
Intelligently tracks subjects (faces) using MediaPipe, smoothing the crop
window dynamically across scenes (PySceneDetect), falling back to Blur-Fill
when subjects are too wide for the new ratio.

Usage:
    python smart_reframe.py --in input.mp4 --ratio 9:16 --out final.mp4
"""

import os
import cv2
import math
import logging
import argparse
import subprocess
import numpy as np
from pathlib import Path

# Try importing dependencies
try:
    import mediapipe as mp
    from scenedetect import detect, ContentDetector
except ImportError as e:
    raise ImportError("Please install dependencies: pip install mediapipe scenedetect opencv-python numpy") from e

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# RATIOS -> (width, height)
TARGET_RESOLUTIONS = {
    "9:16": (1080, 1920),
    "1:1":  (1080, 1080),
    "4:5":  (1080, 1350),
    "16:9": (1920, 1080)
}

def get_ffmpeg_path():
    p = os.path.join("backend", "ffmpeg.exe")
    if os.path.exists(p): return p
    return "ffmpeg"

def parse_ratio(ratio_str):
    if ratio_str in TARGET_RESOLUTIONS:
        return TARGET_RESOLUTIONS[ratio_str]
    # parse custom like "w:h"
    w, h = map(int, ratio_str.split(':'))
    # Normalize to 1080p target width logic
    scale = 1080 / w
    return int(w * scale), int(h * scale)

def detect_scenes(video_path):
    logger.info("Detecting scenes...")
    scenes = detect(video_path, ContentDetector())
    # PySceneDetect returns list of (start_time, end_time) frame units
    scene_frames = [(s[0].get_frames(), s[1].get_frames()) for s in scenes]
    if not scene_frames:
        # Fallback if no cuts: single scene
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        scene_frames = [(0, total)]
    return scene_frames

def extract_faces_for_scene(cap, start_frame, end_frame, sample_rate_fps, fps, orig_w, orig_h, target_w, target_h):
    """
    Run MediaPipe on `sample_rate_fps` per second.
    Returns: 
        decision (str): "TRACKED_CROP", "BLUR_FILL", "STATIC_FALLBACK"
        raw_centers (dict): frame_idx -> (cx, cy)
    """
    mp_face_detection = mp.solutions.face_detection
    
    frame_step = max(1, int(fps / sample_rate_fps))
    raw_centers = {}
    
    crop_w = int(orig_h * (target_w / target_h))
    crop_h = orig_h
    if crop_w > orig_w:
        crop_w = orig_w
        crop_h = int(orig_w * (target_h / target_w))
    
    needs_blur_fill = False
    faces_detected_count = 0
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_det:
        for f in range(start_frame, end_frame, frame_step):
            ret, frame = cap.read()
            if not ret: break
            
            # Mediapipe uses RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_det.process(rgb)
            
            if results.detections:
                faces_detected_count += 1
                min_x = orig_w
                min_y = orig_h
                max_x = 0
                max_y = 0
                
                for detection in results.detections:
                    bboxC = detection.location_data.relative_bounding_box
                    x = int(bboxC.xmin * orig_w)
                    y = int(bboxC.ymin * orig_h)
                    w = int(bboxC.width * orig_w)
                    h = int(bboxC.height * orig_h)
                    
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x + w)
                    max_y = max(max_y, y + h)
                    
                # Group ROI
                roi_w = max_x - min_x
                roi_h = max_y - min_y
                cx = min_x + roi_w / 2
                cy = min_y + roi_h / 2
                
                # Check if group ROI exceeds strict crop bounds
                if roi_w > crop_w * 0.95 or roi_h > crop_h * 0.95:
                    needs_blur_fill = True
                
                raw_centers[f] = (cx, cy)
                
            # fast forward to next step
            cap.set(cv2.CAP_PROP_POS_FRAMES, f + frame_step)
            
    # Decisions
    if faces_detected_count == 0:
        return "STATIC_FALLBACK", {}
    if needs_blur_fill:
        return "BLUR_FILL", {}
    return "TRACKED_CROP", raw_centers

def apply_smoothing(raw_centers, start_frame, end_frame, orig_w, orig_h, fps):
    """
    Interpolate missing frames, then apply Exponential Moving Average (EMA).
    Returns list of dict: {frame_idx: (cx, cy)}
    """
    smoothed = {}
    
    frames_with_data = sorted(list(raw_centers.keys()))
    if not frames_with_data:
        # Upward bias center crop fallback if somehow empty
        fallback_cx = orig_w / 2
        fallback_cy = orig_h / 3
        for i in range(start_frame, end_frame):
            smoothed[i] = (fallback_cx, fallback_cy)
        return smoothed

    # 1. Linear interpolation for missing frames
    raw_interp = {}
    for i in range(start_frame, end_frame):
        if i <= frames_with_data[0]:
            raw_interp[i] = raw_centers[frames_with_data[0]]
        elif i >= frames_with_data[-1]:
            raw_interp[i] = raw_centers[frames_with_data[-1]]
        else:
            # find bounding keys
            left_k = max([k for k in frames_with_data if k <= i])
            right_k = min([k for k in frames_with_data if k >= i])
            if left_k == right_k:
                raw_interp[i] = raw_centers[left_k]
            else:
                ratio = (i - left_k) / (right_k - left_k)
                lx, ly = raw_centers[left_k]
                rx, ry = raw_centers[right_k]
                raw_interp[i] = (lx + (rx-lx)*ratio, ly + (ry-ly)*ratio)
                
    # 2. EMA Smoothing
    ALPHA = 0.05 # Lower = smoother but draggier. 0.05 @ 30fps is ~1.5 sec reaction
    
    # Cap velocity to prevent extreme drags
    max_velocity = orig_w * 0.03 # max 3% screen movement per frame
    
    current_cx, current_cy = raw_interp[start_frame]
    for i in range(start_frame, end_frame):
        target_cx, target_cy = raw_interp[i]
        
        # Apply velocity cap before EMA
        dx = target_cx - current_cx
        dy = target_cy - current_cy
        dist = math.hypot(dx, dy)
        if dist > max_velocity:
            target_cx = current_cx + (dx/dist) * max_velocity
            target_cy = current_cy + (dy/dist) * max_velocity
            
        current_cx = ALPHA * target_cx + (1 - ALPHA) * current_cx
        current_cy = ALPHA * target_cy + (1 - ALPHA) * current_cy
        
        smoothed[i] = (current_cx, current_cy)
        
    return smoothed

def get_real_video_dimensions(file_path):
    ffprobe = os.path.join("backend", "ffprobe.exe")
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json", file_path
    ]
    try:
        import json
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        w, h = int(stream.get("width")), int(stream.get("height"))
        rotate = stream.get("tags", {}).get("rotate")
        if rotate and str(rotate) in ["90", "-90", "270", "-270", "90.0", "-90.0", "270.0", "-270.0"]:
            w, h = h, w
        else:
            for sd in stream.get("side_data_list", []):
                if "rotation" in sd:
                    if abs(int(float(sd["rotation"]))) in [90, 270]:
                        w, h = h, w
        return w, h
    except:
        return None, None

def reframe_video(input_path: str, target_ratio: str, output_path: str) -> str:
    logger.info(f"Reframing {input_path} to {target_ratio}")
    target_w, target_h = parse_ratio(target_ratio)
    
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Use robust rotation-aware dimensions
    w_h = get_real_video_dimensions(input_path)
    if w_h[0]:
        orig_w, orig_h = w_h
    else:
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    
    orig_aspect = orig_w / orig_h
    target_aspect = target_w / target_h
    
    if abs(orig_aspect - target_aspect) < 0.05:
        logger.info("Source is already at or near target ratio. Copying directly.")
        cap.release()
        subprocess.run([get_ffmpeg_path(), "-y", "-i", input_path, "-c", "copy", output_path])
        return output_path

    scenes = detect_scenes(input_path)
    logger.info(f"Found {len(scenes)} discrete scenes/shots.")
    
    crop_w = int(orig_h * target_aspect)
    crop_h = orig_h
    if crop_w > orig_w:
        crop_w = orig_w
        crop_h = int(orig_w / target_aspect)
        
    # Build per-frame plan
    frame_plans = {}
    
    for idx, (start_f, end_f) in enumerate(scenes):
        duration_sec = (end_f - start_f) / fps
        # Short shots don't track well, stick to static center or previous track
        if duration_sec < 0.8:
            logger.info(f"Scene {idx+1}: STATIC (Short shot {duration_sec:.1f}s)")
            for i in range(start_f, end_f):
                frame_plans[i] = ("STATIC_FALLBACK", (orig_w/2, orig_h/3))
            continue
            
        decision, raw_centers = extract_faces_for_scene(cap, start_f, end_f, 5, fps, orig_w, orig_h, target_w, target_h)
        logger.info(f"Scene {idx+1}: {decision}")
        
        if decision == "TRACKED_CROP":
            smoothed = apply_smoothing(raw_centers, start_f, end_f, orig_w, orig_h, fps)
            for i in range(start_f, end_f):
                frame_plans[i] = (decision, smoothed[i])
        else:
            for i in range(start_f, end_f):
                frame_plans[i] = (decision, (orig_w/2, orig_h/3))

    # --- Render Pass via FFmpeg Pipe ---
    logger.info("Starting Video Rendering Pipe...")
    temp_video = "temp_render_noaudio.mp4"
    
    ffmpeg_cmd = [
        get_ffmpeg_path(),
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{target_w}x{target_h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        temp_video
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    for i in range(total_frames):
        ret, frame = cap.read()
        if not ret: break
        
        # Get plan
        plan = frame_plans.get(i, ("STATIC_FALLBACK", (orig_w/2, orig_h/3)))
        decision, center = plan
        
        if decision in ("TRACKED_CROP", "STATIC_FALLBACK"):
            cx, cy = center
            x = int(max(0, min(cx - crop_w / 2, orig_w - crop_w)))
            y = int(max(0, min(cy - crop_h / 2, orig_h - crop_h)))
            
            cropped = frame[y:y+crop_h, x:x+crop_w]
            out_frame = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_AREA)
            
        elif decision == "BLUR_FILL":
            # 1. Background Fill & Blur
            bg = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
            # Heavy box blur for performance
            bg = cv2.blur(bg, (75, 75))
            
            # 2. Foreground scale
            scale = min(target_w / orig_w, target_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            fg = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # 3. Composite center
            off_x = (target_w - new_w) // 2
            off_y = (target_h - new_h) // 2
            bg[off_y:off_y+new_h, off_x:off_x+new_w] = fg
            out_frame = bg
            
        proc.stdin.write(out_frame.tobytes())
        
        if i % (fps * 5) == 0:
            logger.info(f"Render progress: {i}/{total_frames} frames")
            
    proc.stdin.close()
    proc.wait()
    cap.release()
    
    # Remux Audio
    logger.info("Remuxing Audio...")
    remux_cmd = [
        get_ffmpeg_path(),
        "-y",
        "-i", temp_video,
        "-i", input_path,
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:a", "aac",
        "-movflags", "+faststart",
        # Fix missing DAR via lavfi is not needed on copy, but let's set metadata explicitly
        "-aspect", f"{target_w}:{target_h}",
        output_path
    ]
    subprocess.run(remux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(temp_video):
        os.remove(temp_video)
        
    logger.info(f"âœ… Reframed video saved to {output_path}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Auto-Reframe Video")
    parser.add_argument("--in", dest="input", required=True, help="Input video path")
    parser.add_argument("--ratio", default="9:16", help="Target ratio (e.g. 9:16, 1:1, 4:5)")
    parser.add_argument("--out", required=True, help="Output video path")
    args = parser.parse_args()
    
    reframe_video(args.input, args.ratio, args.out)
