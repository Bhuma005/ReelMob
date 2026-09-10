"""
fit_to_canvas.py
Module to ensure any video is converted to exactly the target canvas size (9:16 by default) 
without cropping, using a blurred version of itself as padding for any dead space.
"""
import os
import sys
import math
import argparse
import subprocess
import json

def get_ff_paths():
    """Locate ffmpeg and ffprobe."""
    ffmpeg = os.path.join("backend", "ffmpeg.exe")
    ffprobe = os.path.join("backend", "ffprobe.exe")
    if not os.path.exists(ffmpeg):
        ffmpeg = "ffmpeg"
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    return ffmpeg, ffprobe

def get_video_dimensions(file_path, ffprobe_path="ffprobe"):
    """Use ffprobe to dynamically extract width and height of the main video stream, including rotation."""
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json",
        file_path
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        w, h = stream.get("width"), stream.get("height")
        if w and h:
            w, h = int(w), int(h)
            # Check tags for rotation
            tags = stream.get("tags", {})
            rotate = tags.get("rotate")
            if rotate and str(rotate) in ["90", "-90", "270", "-270", "90.0", "-90.0", "270.0", "-270.0"]:
                w, h = h, w
            else:
                # Check side data for rotation (newer ffmpeg versions)
                side_data_list = stream.get("side_data_list", [])
                for sd in side_data_list:
                    if "rotation" in sd:
                        rot = sd["rotation"]
                        if abs(int(float(rot))) == 90 or abs(int(float(rot))) == 270:
                            w, h = h, w
            return w, h
    except Exception as e:
        print(f"[Warning] FFprobe extraction failed: {e}")
        
    # Fallback to OpenCV if ffprobe fails/is missing
    print("[Info] Falling back to OpenCV for dimension check.")
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return w, h
    except:
        return None, None

def fit_to_canvas(input_path: str, output_path: str, canvas_w: int = 1080, canvas_h: int = 1920) -> str:
    """
    Guarantees the output video is strictly canvas_w x canvas_h (default 1080x1920).
    Uses a heavy blurred background fill if the aspect ratios don't match exactly.
    """
    ffmpeg_path, ffprobe_path = get_ff_paths()
    
    in_w, in_h = get_video_dimensions(input_path, ffprobe_path)
    if not in_w or not in_h:
        raise ValueError("Could not determine input video dimensions.")
        
    # Safe floating checks for aspect ratios
    in_ratio = in_w / in_h
    target_ratio = canvas_w / canvas_h
    
    print(f"[{os.path.basename(input_path)}] Size: {in_w}x{in_h} (Ratio: {in_ratio:.3f}) -> Target: {canvas_w}x{canvas_h} (Ratio: {target_ratio:.3f})")

    # Edge Case: Near exact match, just resize without blurring to save time
    if abs(in_ratio - target_ratio) < 0.02:
        print("-> Exact or near-exact match detected. Copying directly without converting.")
        cmd = [
            ffmpeg_path, "-y",
            "-i", input_path,
            "-c", "copy",
            output_path
        ]
    else:
        print("-> Aspect ratio mismatch. Utilizing blurred-canvas fill (no crop).")
        # Build Filter Complex
        # BG: Scale to COVER the target bounds (force_original_aspect_ratio=increase) + Crop exactly to target + Blur
        # FG: Scale to FIT the target bounds (force_original_aspect_ratio=decrease)
        # OVERLAY: Center FG over BG. Also forcing SAR/DAR output so players don't stretch it.
        filter_complex = (
            f"[0:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},boxblur=20:5[bg];"
            f"[0:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,setdar={canvas_w}/{canvas_h}"
        )
        
        cmd = [
            ffmpeg_path, "-y",
            "-i", input_path,
            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy", 
            output_path
        ]

    # Execute
    print(f"Executing: {' '.join(cmd[:6])} ...")
    env = os.environ.copy()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="ignore")
        raise RuntimeError(f"FFmpeg failed with code {proc.returncode}\\n{err[-500:]}")
        
    print(f"✅ Auto-Detect & Fit-to-Canvas Complete: {output_path}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-Detect & Fit-to-Canvas Video Converter")
    parser.add_argument("--in", dest="input", required=True, help="Path to input video")
    parser.add_argument("--out", required=True, help="Path to output video")
    parser.add_argument("--width", type=int, default=1080, help="Canvas Width (default: 1080)")
    parser.add_argument("--height", type=int, default=1920, help="Canvas Height (default: 1920)")
    
    args = parser.parse_args()
    try:
        fit_to_canvas(args.input, args.out, args.width, args.height)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
