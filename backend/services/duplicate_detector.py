"""
duplicate_detector.py — Perceptual Video Hashing and Duplicate Detection.
Computes 64-bit difference hash (dHash) using PIL/OpenCV to identify identical
or near-duplicate videos across the creator's video library.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from PIL import Image

from backend.fit_to_canvas import get_ff_paths
from backend.services.video_editor import get_video_duration

logger = logging.getLogger("reelsmob.duplicates")

# In-memory registry fallback for local dev & testing
LOCAL_HASH_REGISTRY: Dict[str, Dict[str, Any]] = {}


def compute_image_dhash(image: Image.Image) -> str:
    """
    Computes a 64-bit difference hash (dHash) from a PIL Image.
    1. Grayscale conversion.
    2. Resize to 9x8.
    3. Compare adjacent horizontal pixels (8 rows x 8 comparisons = 64 bits).
    4. Format as 16-character hexadecimal string.
    """
    # Convert to grayscale
    gray = image.convert("L")
    # Resize to 9 width x 8 height (LANCZOS or default BILINEAR)
    resized = gray.resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(resized.getdata())

    # 64-bit integer
    diff_bits = 0
    for row in range(8):
        row_offset = row * 9
        for col in range(8):
            left_pixel = pixels[row_offset + col]
            right_pixel = pixels[row_offset + col + 1]
            diff_bits <<= 1
            if left_pixel > right_pixel:
                diff_bits |= 1

    return f"{diff_bits:016x}"


def compute_video_perceptual_hash(video_path: str, url: Optional[str] = None) -> str:
    """
    Computes primary perceptual dHash for a video file by sampling keyframes.
    Returns 16-character hexadecimal string.
    """
    candidate_paths = [
        video_path,
        os.path.join("downloads", video_path) if video_path else None,
        os.path.join("downloads", os.path.basename(video_path)) if video_path else None
    ]
    resolved_path = None
    for p in candidate_paths:
        if p and os.path.exists(p) and os.path.isfile(p):
            resolved_path = p
            break

    downloaded_temp_video = None
    if not resolved_path:
        if url and url.strip():
            logger.info(f"Local video not found for perceptual hash. Downloading on-demand from: {url}")
            from backend.services.video_download import ensure_video_downloaded
            resolved_path = ensure_video_downloaded(url.strip(), prefix="dup_")
            downloaded_temp_video = resolved_path
        else:
            raise FileNotFoundError(f"Video file not found at: {video_path}")

    try:
        ffmpeg_path, ffprobe_path = get_ff_paths()
        duration = get_video_duration(resolved_path, ffprobe_path)

        # Frame extraction via OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(resolved_path)
            try:
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    if duration <= 0 and total_frames > 0:
                        duration = total_frames / fps

                    # Sample at mid-point (50%)
                    mid_frame = max(0, int(total_frames * 0.5)) if total_frames > 0 else 0
                    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
                    ret, frame = cap.read()

                    if ret and frame is not None:
                        # Convert BGR OpenCV image to RGB PIL image
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(rgb_frame)
                        return compute_image_dhash(pil_img)
            finally:
                cap.release()
        except Exception as exc:
            logger.warning(f"OpenCV frame capture for hash failed: {exc}")

        # If OpenCV failed or wasn't available, try ffmpeg thumbnail extraction
        import tempfile
        import subprocess

        temp_img = tempfile.mktemp(suffix=".jpg")
        try:
            sample_time = max(0.1, duration * 0.5) if duration > 0 else 0.5
            cmd = [
                ffmpeg_path,
                "-y",
                "-ss", str(sample_time),
                "-i", resolved_path,
                "-vframes", "1",
                "-q:v", "2",
                temp_img
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(temp_img) and os.path.getsize(temp_img) > 0:
                with Image.open(temp_img) as img:
                    return compute_image_dhash(img)
        except Exception as exc:
            logger.error(f"FFmpeg frame extraction for hash failed: {exc}")
        finally:
            if os.path.exists(temp_img):
                try:
                    os.remove(temp_img)
                except Exception:
                    pass

        raise ValueError(f"Could not compute perceptual hash for {video_path}")
    finally:
        # Clean up temporary on-demand downloaded video
        if downloaded_temp_video and os.path.exists(downloaded_temp_video):
            try:
                os.remove(downloaded_temp_video)
            except Exception:
                pass


def hamming_distance(hash1: str, hash2: str) -> int:
    """Computes the Hamming distance (number of bit differences) between two 16-char hex hashes."""
    if not hash1 or not hash2:
        return 64
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count("1")
    except ValueError:
        return 64


def register_video_hash(video_id: str, title: str, hash_val: str):
    """Registers a video hash in both memory and Supabase (if configured)."""
    if len(LOCAL_HASH_REGISTRY) >= 1000:
        LOCAL_HASH_REGISTRY.pop(next(iter(LOCAL_HASH_REGISTRY)), None)
    LOCAL_HASH_REGISTRY[video_id] = {
        "id": video_id,
        "title": title,
        "perceptual_hash": hash_val
    }

    try:
        from cloud.cloud_auth import get_supabase_client
        sb = get_supabase_client()
        sb.table("video_library").update({"perceptual_hash": hash_val}).eq("id", video_id).execute()
    except Exception as exc:
        logger.debug(f"Supabase hash update skipped or failed: {exc}")


def check_video_duplicate(video_path: str, threshold: int = 10, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Checks if the target video is a duplicate or near-duplicate of any video in video_library.
    Returns:
    {
        "is_duplicate": bool,
        "hash": str,
        "matches": [
            {"id": str, "title": str, "distance": int, "similarity_pct": float, "created_at": str}
        ]
    }
    """
    video_hash = compute_video_perceptual_hash(video_path, url=url)

    existing_videos: List[Dict[str, Any]] = []

    # 1. Fetch library from Supabase
    try:
        from cloud.cloud_auth import get_supabase_client
        sb = get_supabase_client()
        res = sb.table("video_library").select("id, title, perceptual_hash, created_at").not_.is_("perceptual_hash", "null").execute()
        if res and res.data:
            existing_videos.extend(res.data)
    except Exception as exc:
        logger.debug(f"Could not query Supabase video_library for duplicate check: {exc}")

    # 2. Add local in-memory records (avoiding duplicate IDs)
    seen_ids = {str(v.get("id")) for v in existing_videos}
    for item_id, item in LOCAL_HASH_REGISTRY.items():
        if item_id not in seen_ids and item.get("perceptual_hash"):
            existing_videos.append(item)

    matches = []
    for item in existing_videos:
        stored_hash = item.get("perceptual_hash")
        if not stored_hash:
            continue

        dist = hamming_distance(video_hash, stored_hash)
        if dist <= threshold:
            similarity_pct = round(((64 - dist) / 64.0) * 100.0, 1)
            matches.append({
                "id": str(item.get("id")),
                "title": str(item.get("title") or "Existing Video"),
                "distance": dist,
                "similarity_pct": similarity_pct,
                "created_at": item.get("created_at")
            })

    # Sort matches by closest distance (highest visual similarity)
    matches.sort(key=lambda m: m["distance"])

    return {
        "is_duplicate": len(matches) > 0,
        "hash": video_hash,
        "matches": matches
    }
