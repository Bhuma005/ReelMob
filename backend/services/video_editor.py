"""
video_editor.py — In-app video editing engine powered by FFmpeg.
Supports trimming, color grading (eq filter), caption burn-in,
watermark overlays, and aspect framing (blur pad vs crop).
"""

import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from backend.fit_to_canvas import get_ff_paths, get_video_dimensions

logger = logging.getLogger("reelsmob.editor")


def _escape_drawtext(text: str) -> str:
    """Escapes special characters for FFmpeg drawtext filter."""
    if not text:
        return ""
    # In FFmpeg filter graph, \, ', :, %, [ ] need escaping
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def get_video_duration(file_path: str, ffprobe_path: str = "ffprobe") -> float:
    """Extracts duration in seconds using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        file_path
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(proc.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception as exc:
        logger.warning(f"Could not probe duration for {file_path}: {exc}")
        return 0.0


def process_video_edit(
    input_path: str,
    output_path: str,
    trim: Optional[Dict[str, float]] = None,
    color: Optional[Dict[str, float]] = None,
    captions: Optional[Dict[str, Any]] = None,
    watermark: Optional[Dict[str, Any]] = None,
    framing: str = "original",  # "original" | "blur_pad" | "crop"
    target_width: int = 1080,
    target_height: int = 1920
) -> Dict[str, Any]:
    """
    Applies video edits in a single FFmpeg pass:
    - trim: {"start": float, "end": float}
    - color: {"brightness": -0.5..0.5, "contrast": 0.5..2.0, "saturation": 0.0..2.0}
    - captions: {"text": str, "font_size": int, "position": "top"|"center"|"bottom", "color": str}
    - watermark: {"text": str, "position": "top-left"|"top-right"|"bottom-left"|"bottom-right", "opacity": float}
    - framing: "original" | "blur_pad" | "crop"
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video does not exist: {input_path}")

    ffmpeg_path, ffprobe_path = get_ff_paths()
    total_duration = get_video_duration(input_path, ffprobe_path)

    cmd = [ffmpeg_path, "-y"]

    # 1. Trimming via input seeking
    start_time = 0.0
    end_time = total_duration
    if trim:
        start_time = max(0.0, float(trim.get("start", 0.0)))
        if "end" in trim and float(trim["end"]) > start_time:
            end_time = min(total_duration, float(trim["end"])) if total_duration > 0 else float(trim["end"])
        if start_time > 0:
            cmd.extend(["-ss", f"{start_time:.3f}"])
        if end_time > start_time:
            cmd.extend(["-to", f"{end_time:.3f}"])

    cmd.extend(["-i", input_path])

    # 2. Build Video Filter Graph
    video_filters = []

    # A. Framing
    if framing == "blur_pad":
        # Complex blur fill to 9:16 target canvas
        # Scale background to fill + blur + scale foreground to fit + overlay
        pass  # We handle this via filter_complex below if selected
    elif framing == "crop":
        video_filters.append(
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height}"
        )

    # B. Color Adjustment (eq filter)
    if color:
        b = max(-0.5, min(0.5, float(color.get("brightness", 0.0))))
        c = max(0.5, min(2.0, float(color.get("contrast", 1.0))))
        s = max(0.0, min(2.0, float(color.get("saturation", 1.0))))
        if b != 0.0 or c != 1.0 or s != 1.0:
            video_filters.append(f"eq=brightness={b:.2f}:contrast={c:.2f}:saturation={s:.2f}")

    # C. Caption Burn-In (drawtext)
    if captions and captions.get("text"):
        cap_text = _escape_drawtext(captions["text"].strip())
        if cap_text:
            font_size = max(14, min(72, int(captions.get("font_size", 36))))
            font_color = captions.get("color", "white")
            pos = captions.get("position", "bottom")
            if pos == "top":
                y_pos = "80"
            elif pos == "center":
                y_pos = "(h-text_h)/2"
            else:
                y_pos = "h-text_h-100"

            video_filters.append(
                f"drawtext=text='{cap_text}':fontcolor={font_color}:fontsize={font_size}:"
                f"x=(w-text_w)/2:y={y_pos}:box=1:boxcolor=black@0.65:boxborderw=10"
            )

    # D. Watermark Overlay (drawtext)
    if watermark and watermark.get("text"):
        wm_text = _escape_drawtext(watermark["text"].strip())
        if wm_text:
            opacity = max(0.1, min(1.0, float(watermark.get("opacity", 0.75))))
            pos = watermark.get("position", "bottom-right")
            if pos == "top-left":
                coord = "x=30:y=30"
            elif pos == "top-right":
                coord = "x=w-text_w-30:y=30"
            elif pos == "bottom-left":
                coord = "x=30:y=h-text_h-30"
            else:
                coord = "x=w-text_w-30:y=h-text_h-30"

            video_filters.append(
                f"drawtext=text='{wm_text}':fontcolor=white@{opacity:.2f}:fontsize=22:{coord}:"
                f"box=1:boxcolor=black@{opacity * 0.5:.2f}:boxborderw=4"
            )

    # 3. Assemble Command
    if framing == "blur_pad":
        # Multi-stream filter complex for blur pad + chaining remaining filters
        base_blur = (
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},boxblur=20:5[bg];"
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[framed]"
        )
        if video_filters:
            post_filters = ",".join(video_filters)
            full_complex = f"{base_blur};[framed]{post_filters},setsar=1,setdar={target_width}/{target_height}[v]"
        else:
            full_complex = f"{base_blur};[framed]setsar=1,setdar={target_width}/{target_height}[v]"

        cmd.extend(["-filter_complex", full_complex, "-map", "[v]", "-map", "0:a?"])
    else:
        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])
        cmd.extend(["-map", "0:v", "-map", "0:a?"])

    # Output encoding parameters
    cmd.extend([
        "-threads", "2",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ])

    logger.info(f"Executing video edit: {' '.join(cmd[:8])} ...")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        err_msg = proc.stderr[-800:] if proc.stderr else "Unknown error"
        logger.error(f"FFmpeg edit execution failed: {err_msg}")
        raise RuntimeError(f"FFmpeg processing failed: {err_msg}")

    # Probe final output
    out_w, out_h = get_video_dimensions(output_path, ffprobe_path)
    out_dur = get_video_duration(output_path, ffprobe_path)
    out_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

    return {
        "output_path": output_path,
        "width": out_w,
        "height": out_h,
        "duration": out_dur,
        "size_bytes": out_size,
    }
