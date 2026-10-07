"""A small, provider-independent tool-calling boundary."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """One requested tool operation."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    """Tool calls and metered provider usage."""

    calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    """Clients must use a bounded timeout and must not own database credentials."""

    model: str

    async def complete(
        self,
        messages: list[dict[str, Any]],
        schemas: list[dict[str, object]],
        timeout: float,
    ) -> ModelReply:
        """Return normalized tool calls within the remaining run budget."""
        ...

    async def aclose(self) -> None:
        """Release provider resources after the enclosing run."""
        ...
