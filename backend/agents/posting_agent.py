import logging
from backend.agents.base import BaseAgent, AgentState
from backend.posting_engine import get_best_posting_time

logger = logging.getLogger(__name__)

class PostingIntelligenceAgent(BaseAgent):
    """
    Deterministic Posting Engine wrapped as an agent step.
    DOES NOT use an LLM.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("PostingIntelligenceAgent calculating best slot...")
        
        # We can extract topic or category from the content agent if available
        content = state.get("content", {})
        topic = content.get("topic")
        category = content.get("category")
        
        try:
            posting_intel = get_best_posting_time(topic=topic, category=category)
            
            # Reformat to store in state clearly
            recommended_slot = posting_intel.get("scored_slots", [{}])[0] if posting_intel.get("scored_slots") else {}
            
            state.update("posting", {
                "status": posting_intel.get("status", "NO_DATA"),
                "confidence": posting_intel.get("confidence", "LOW"),
                "recommended_slot": recommended_slot,
                "scored_slots": posting_intel.get("scored_slots", []),
                "human_readable_time": posting_intel.get("human_readable_time", "07:30 PM")
            })
        except Exception as e:
            logger.error(f"Posting engine failed: {e}")
            state.update("posting", {"status": "failed", "error": str(e)})
            
        return state
