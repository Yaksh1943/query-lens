"""
Base Agent Interface Protocol.

Establishes the typed contract for specialized QueryLens agents.
"""
from typing import Protocol

from app.agents.state import AgentState


class Agent(Protocol):
    """Universal protocol implemented by all specialized QueryLens agents."""

    def run(self, state: AgentState) -> AgentState:
        """Processes and mutates the agent state, returning the updated state."""
        ...
