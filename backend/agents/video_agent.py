import logging
from backend.agents.base import BaseAgent, AgentState
import yt_dlp
import asyncio

logger = logging.getLogger(__name__)

class VideoIntelligenceAgent(BaseAgent):
    """
    Analyzes the video using existing tools (yt-dlp).
    Determines dimensions, aspect ratio, audio availability.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("VideoIntelligenceAgent analyzing video properties...")
        
        url = state.get("url")
        if not url:
            logger.info("No URL provided, skipping video extraction.")
            state.update("video", {"status": "skipped", "reason": "No URL provided"})
            return state

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("yt-dlp returned None")
                    
                w = info.get('width')
                h = info.get('height')
                fps = info.get('fps')
                duration = info.get('duration')
                vcodec = info.get('vcodec')
                
                # Aspect ratio
                aspect_ratio = "Unknown"
                if w and h:
                    import math
                    if w == 1080 and h == 1920: aspect_ratio = "9:16"
                    elif w == 1920 and h == 1080: aspect_ratio = "16:9"
                    elif w == 1080 and h == 1350: aspect_ratio = "4:5"
                    elif w == 1080 and h == 1080: aspect_ratio = "1:1"
                    else:
                        g = math.gcd(w, h)
                        aspect_ratio = f"{w//g}:{h//g}"
                
                video_data = {
                    "width": w,
                    "height": h,
                    "aspect_ratio": aspect_ratio,
                    "fps": fps,
                    "duration": duration,
                    "vcodec": vcodec,
                    "status": "success"
                }
                logger.info(f"Video data extracted: {video_data}")
                state.update("video", video_data)
                
        except Exception as e:
            logger.error(f"Video extraction failed: {e}")
            state.update("video", {"status": "failed", "error": str(e)})

        return state
