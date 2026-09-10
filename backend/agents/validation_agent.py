import logging
import os
from backend.agents.base import BaseAgent, AgentState

logger = logging.getLogger(__name__)

class ValidationAgent(BaseAgent):
    """
    Deterministic agent that validates everything before user approval/scheduling.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("ValidationAgent verifying workflow state...")
        
        errors = []
        warnings = []
        
        # 1. Video Validation
        video = state.get("video", {})
        if video.get("status") == "failed":
            errors.append("Video analysis failed.")
        elif video.get("status") == "success":
            w = video.get("width", 0)
            h = video.get("height", 0)
            if w > h:
                warnings.append("Video is horizontal (16:9). YouTube Shorts prefers 9:16 or 1:1.")
        
        # 2. Metadata Validation
        metadata = state.get("metadata", {})
        if not metadata.get("best_title"):
            errors.append("Missing generated title.")
            
        # 3. YouTube Validation
        # Check if client_secrets.json exists for auth
        if not os.path.exists("backend/client_secrets.json") and not os.path.exists("backend/youtube_credentials.json"):
            warnings.append("YouTube OAuth credentials not fully configured.")
            
        if errors:
            state.update("validation", {"status": "failed", "errors": errors, "warnings": warnings})
        else:
            state.update("validation", {"status": "passed", "warnings": warnings})
            
        return state
