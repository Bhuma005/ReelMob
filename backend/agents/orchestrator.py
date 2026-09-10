import logging
from backend.agents.base import AgentState
from typing import List

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """Manages the ReelGrab AI Workflow."""
    
    def __init__(self, agents: List = None):
        self.agents = agents or []
        
    def execute(self, initial_state: dict) -> AgentState:
        state = AgentState(initial_state)
        logger.info(f"Orchestrator starting job {state.get('job_id')} with {len(self.agents)} agents.")
        
        for agent in self.agents:
            logger.info(f"Running agent: {agent.name}")
            try:
                state = agent.run(state)
            except Exception as e:
                logger.error(f"Agent {agent.name} failed: {e}")
                state.update("status", {"error": str(e), "failed_agent": agent.name})
                break
                
        state.update("status", {"completed": True})
        return state
