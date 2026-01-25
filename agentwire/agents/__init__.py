"""Agent backends for managing AI coding sessions."""

from .base import AgentBackend
from .tmux import TmuxAgent

__all__ = ["AgentBackend", "TmuxAgent", "get_agent_backend"]


def get_agent_backend(config: dict) -> AgentBackend:
    """Get the appropriate agent backend based on config.

    Args:
        config: Configuration dict

    Returns:
        AgentBackend instance (currently always TmuxAgent)
    """
    # Only tmux backend implemented for now
    return TmuxAgent(config)
