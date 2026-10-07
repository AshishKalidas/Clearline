"""Explicit provider selection. No live request is made by the offline baseline."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from backend.app.agent.llm.anthropic_client import AnthropicLLM
from backend.app.agent.llm.base import LLMClient
from backend.app.agent.llm.openai_compat import OpenAICompatLLM
from backend.app.agent.llm.stub import StubLLM
from backend.app.config import Settings


def create_client(settings: Settings) -> LLMClient:
    """Construct the requested provider; refuse unsupported or unconfigured live calls."""
    if settings.llm_provider == "stub":
        return StubLLM()
    if settings.llm_provider == "claude":
        return AnthropicLLM(settings)
    return OpenAICompatLLM(settings)


@asynccontextmanager
async def client_scope(settings: Settings) -> AsyncIterator[LLMClient]:
    """Close shared provider transports even if a reconciliation run is cancelled."""
    client = create_client(settings)
    try:
        yield client
    finally:
        await client.aclose()
