import logging
from backend.agents.base import BaseAgent, AgentState
from backend.agents.llm import call_ollama

logger = logging.getLogger(__name__)

class AnalyticsIntelligenceAgent(BaseAgent):
    """
    Qwen acts ONLY as an explanation layer for the deterministic posting engine.
    It does NOT invent or change the scheduled time.
    """
    def run(self, state: AgentState) -> AgentState:
        logger.info("AnalyticsIntelligenceAgent explaining deterministic schedule...")
        
        posting_data = state.get("posting", {})
        if not posting_data or posting_data.get("status") == "INSUFFICIENT_DATA":
            logger.info("Insufficient data for detailed explanation.")
            state.update("analytics", {"reasoning": "Test slots recommended due to lack of historical data."})
            return state
            
        recommended = posting_data.get("recommended_slot")
        if not recommended:
            return state
            
        system_prompt = (
            "You are ReelGrab's Analytics Intelligence Agent.\n"
            "Your ONLY job is to explain why the deterministic posting engine chose the provided time.\n"
            "DO NOT change the time. DO NOT invent fake analytics. DO NOT guarantee virality.\n"
            "Output JSON exactly matching this schema:\n"
            "{\n"
            '  "reasoning": "Clear, concise explanation of why this time is optimal based on the data provided."\n'
            "}"
        )
        
        user_prompt = f"RECOMMENDED TIME: {recommended.get('time')} on {recommended.get('date')}\nSCORE: {recommended.get('score')}\nCONFIDENCE: HIGH\n"
        
        parsed = call_ollama(
            model="qwen2.5:7b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )
        
        if parsed and parsed.get("reasoning"):
            state.update("analytics", {"reasoning": parsed.get("reasoning")})
        else:
            state.update("analytics", {"reasoning": "Optimal time selected based on historical audience activity."})
            
        return state
