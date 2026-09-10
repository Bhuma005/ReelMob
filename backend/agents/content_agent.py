import logging
import json
from backend.agents.base import BaseAgent, AgentState
from backend.agents.llm import call_ollama

logger = logging.getLogger(__name__)

class ContentIntelligenceAgent(BaseAgent):
    """
    Analyzes the transcript and source metadata to extract topics, hooks, and audience.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("ContentIntelligenceAgent extracting meaning...")
        
        raw_title = state.get("raw_title", "")
        raw_description = state.get("raw_description", "")
        transcript = state.get("transcript_text", "")
        
        system_prompt = (
            "You are ReelGrab's Content Intelligence Agent.\n"
            "Analyze the provided video text (title, description, transcript) and extract structured insights.\n"
            "Return JSON matching exactly this schema:\n"
            "{\n"
            '  "topic": "string",\n'
            '  "category": "string",\n'
            '  "content_type": "string",\n'
            '  "language": "string",\n'
            '  "emotion": "string",\n'
            '  "tone": "string",\n'
            '  "hook": "string",\n'
            '  "audience": ["string"],\n'
            '  "entities": ["string"],\n'
            '  "keywords": ["string"]\n'
            "}\n"
            "If information is unknown, use 'unknown'. NEVER hallucinate entities."
        )
        
        user_prompt = f"TITLE:\n{raw_title}\n\nDESCRIPTION:\n{raw_description}\n\nTRANSCRIPT:\n{transcript}"
        
        parsed = call_ollama(
            model="qwen2.5:7b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )
        
        if not parsed:
            logger.warning("Content analysis failed or returned empty.")
            state.update("content", {"status": "failed"})
        else:
            parsed["status"] = "success"
            state.update("content", parsed)
            
        return state
