# Smart Reframe Module

The `smart_reframe.py` module is a standalone, production-ready pipeline step designed to intelligently reframe videos (e.g., 16:9 to 9:16) while behaving similarly to CapCut's "Auto Reframe" feature. It handles face tracking, smooth cinematic camera panning, and fallback safety boundaries.

## Pipeline Architecture

1. **Scene Detection (PySceneDetect)**: The video is first split into discrete shots based on hard visual edits. This ensures the crop window never "drags" across a cut.
2. **Detection & Sampling (MediaPipe + OpenCV)**: We sample frames at a fixed rate (e.g., 5 fps) to save CPU cycles. MediaPipe detects all faces in the frame.
    * Multiple faces in proximity are aggregated into a single Group ROI (Region of Interest) bounding box. 
3. **Decision Logic & Fallback**:
    * **`TRACKED_CROP`**: If the Group ROI is small enough to fit inside the strict bounds of the target aspect ratio, the pipeline marks the scene for smart cropping.
    * **`BLUR_FILL`**: If the ROI exceeds the target crop window (e.g., a wide shot of two separated speakers), a rigid crop would cut someone out. The scene falls back to rendering a blurred, fully-scaled background, overlaying the full sharp video in the center (the "Instagram Story" look).
    * **`STATIC_FALLBACK`**: Used on very short shots (under 0.8s) or scenes with zero faces, relying on a static center-crop with a slight vertical upward bias (better tailored for general talking-head content than absolute center-crop).
4. **Temporal Smoothing**: The tracked target coordinates run through an **Exponential Moving Average (EMA)** filter, clamped dynamically by a max-velocity constraint. This mathematically guarantees the crop window glides smoothly like a gimbal, eliminating jitter while preventing subjects from outrunning the crop box during fast handheld pans.
5. **Render Pass**: We render the video block exactly frame-by-frame using OpenCV. Image arrays are piped via stdout directly into an internal `ffmpeg` subprocess to immediately encode to standard 1080p `libx264` MP4s in a memory-efficient manner. Original audio is then remuxed back in seamlessly.

## Usage

You can slot `reframe_video(input, ratio, output)` straight into a python background queue, or test it standalone via the CLI wrapper:
```bash
python smart_reframe.py --in my_landscape_video.mp4 --ratio 9:16 --out final_shorts.mp4
```
