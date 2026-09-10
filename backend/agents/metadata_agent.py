import logging
from backend.agents.base import BaseAgent, AgentState
from backend.agents.llm import call_ollama

logger = logging.getLogger(__name__)

class MetadataIntelligenceAgent(BaseAgent):
    """
    Generates 10 title candidates and separated hashtags based on content analysis.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("MetadataIntelligenceAgent generating titles and hashtags...")
        
        content = state.get("content", {})
        raw_title = state.get("raw_title", "")
        raw_description = state.get("raw_description", "")
        
        if content.get("status") == "failed":
            logger.warning("Content analysis was missing, metadata might be less accurate.")
            
        system_prompt = (
            "You are ReelGrab's Advanced YouTube Shorts Metadata Intelligence Engine.\n"
            "Generate 10 diverse title strategies (Curiosity, Emotional, Search, Story, Relatable, Unexpected, Question, Short, Entertainment, Natural).\n"
            "Score each title internally and select the strongest as 'best_title'.\n"
            "Generate an engaging 'description'.\n"
            "Generate up to 15 'youtube_hashtags' and up to 30 'instagram_hashtags'.\n"
            "DO NOT use generic clickbait like 'Video by creator' or 'Must Watch'.\n\n"
            "Output JSON exactly matching this schema:\n"
            "{\n"
            '  "title_candidates": [{"title": "string", "strategy": "string", "score": 95}],\n'
            '  "best_title": "string",\n'
            '  "viewer_appeal_score": 95,\n'
            '  "title_reason": "Why this title was chosen",\n'
            '  "description": "string",\n'
            '  "youtube_hashtags": ["#string"],\n'
            '  "instagram_hashtags": ["#string"]\n'
            "}"
        )
        
        user_prompt = f"RAW TITLE:\n{raw_title}\n\nRAW DESC:\n{raw_description}\n\nCONTENT ANALYSIS:\n{content}"
        
        parsed = call_ollama(
            model="qwen2.5:7b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8
        )
        
        if not parsed:
            logger.warning("Metadata generation failed.")
            state.update("metadata", {"status": "failed"})
        else:
            parsed["status"] = "success"
            
            # Simple deduping logic like before
            yt = parsed.get("youtube_hashtags", [])
            ig = parsed.get("instagram_hashtags", [])
            
            seen = set()
            clean_yt = []
            clean_ig = []
            
            for t in yt:
                norm = t.lower().strip()
                if not norm.startswith("#"): norm = "#" + norm
                if norm not in seen:
                    seen.add(norm)
                    clean_yt.append(t.strip())
                    
            for t in ig:
                norm = t.lower().strip()
                if not norm.startswith("#"): norm = "#" + norm
                if norm not in seen:
                    seen.add(norm)
                    clean_ig.append(t.strip())
                    
            parsed["youtube_hashtags"] = clean_yt[:15]
            parsed["instagram_hashtags"] = clean_ig[:30]
            
            state.update("metadata", parsed)
            
        return state
