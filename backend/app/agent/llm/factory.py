"""Explicit provider selection. No live request is made by the offline baseline."""

from backend.app.agent.llm.base import LLMClient
from backend.app.agent.llm.stub import StubLLM
from backend.app.config import Settings


def create_client(settings: Settings) -> LLMClient:
    """Construct the requested provider; refuse unsupported or unconfigured live calls."""
    if settings.llm_provider == "stub":
        return StubLLM()
    raise ValueError("Live provider adapters require the M8 configuration")
