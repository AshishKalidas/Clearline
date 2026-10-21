"""MiMo adapter for a configured OpenAI-compatible Chat Completions endpoint."""

import json
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from backend.app.agent.llm.base import ModelReply, ToolCall
from backend.app.config import Settings
from backend.app.privacy.masking import Masker


def parse_arguments(raw: str) -> dict[str, Any]:
    """Turn malformed provider arguments into a schema error the loop can explain."""
    try:
        value = json.loads(raw)
    except ValueError:
        return {"_invalid_arguments": True}
    return value if isinstance(value, dict) else {"_invalid_arguments": True}


class OpenAICompatLLM:
    """Opt-in MiMo client; the exact model ID must come from MIMO_MODEL."""

    def __init__(self, settings: Settings, sdk: AsyncOpenAI | None = None) -> None:
        if not settings.mimo_model:
            raise ValueError("MIMO_MODEL must be configured; no model ID is guessed")
        if sdk is None and (not settings.mimo_api_key or not settings.mimo_base_url):
            raise ValueError("MIMO_API_KEY and MIMO_BASE_URL are required")
        self.model = settings.mimo_model
        self.sdk = sdk or AsyncOpenAI(
            api_key=settings.mimo_api_key.get_secret_value(),
            base_url=settings.mimo_base_url,
            timeout=15,
            max_retries=2,
        )

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        """Translate the common schema and meter tokens from compatible responses."""
        safe = Masker().clean(messages)
        transcript = cast(
            list[ChatCompletionMessageParam],
            [{key: value for key, value in m.items() if key != "name"} for m in safe],
        )
        tools = cast(
            list[ChatCompletionToolParam], [{"type": "function", "function": s} for s in schemas]
        )
        response = await self.sdk.with_options(timeout=min(timeout, 15)).chat.completions.create(
            model=self.model,
            messages=transcript,
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )
        calls = []
        for choice in response.choices:
            for call in choice.message.tool_calls or []:
                if call.type == "function":
                    calls.append(
                        ToolCall(
                            call.id, call.function.name, parse_arguments(call.function.arguments)
                        )
                    )
        usage = response.usage
        return ModelReply(
            calls, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0
        )

    async def aclose(self) -> None:
        """Release the provider connection pool after a run."""
        await self.sdk.close()
