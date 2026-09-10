import uuid
from typing import Dict, Any, Optional

class AgentState:
    """Structured state passed between agents."""
    def __init__(self, initial_data: Dict[str, Any] = None):
        self.data = {
            "job_id": str(uuid.uuid4()),
            "status": "initialized",
            "video": {},
            "transcript": {},
            "content": {},
            "metadata": {},
            "analytics": {},
            "posting": {},
            "validation": {},
            "publishing": {},
            "learning": {}
        }
        if initial_data:
            self.data.update(initial_data)

    def get(self, key: str, default=None) -> Any:
        return self.data.get(key, default)

    def update(self, key: str, value: Dict[str, Any]):
        if key in self.data and isinstance(self.data[key], dict):
            self.data[key].update(value)
        else:
            self.data[key] = value

class BaseAgent:
    """Base class for all ReelGrab Intelligence Agents."""
    
    def __init__(self):
        self.name = self.__class__.__name__

    def run(self, state: AgentState) -> AgentState:
        """Execute the agent's logic on the state."""
        raise NotImplementedError("Agents must implement the run method.")
