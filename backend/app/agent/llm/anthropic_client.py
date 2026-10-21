"""Anthropic Messages adapter with real SDK retries and normalized tool calls."""

import json
from typing import Any, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam

from backend.app.agent.llm.base import ModelReply, ToolCall
from backend.app.config import Settings
from backend.app.privacy.masking import Masker


def anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[MessageParam]]:
    """Translate normalized transcripts, grouping adjacent tool results correctly."""
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    translated: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "system":
            continue
        if role == "tool":
            result = json.loads(message["content"])
            block = {
                "type": "tool_result",
                "tool_use_id": message["tool_call_id"],
                "content": message["content"],
                "is_error": isinstance(result, dict) and "error" in result,
            }
            if (
                translated
                and translated[-1]["role"] == "user"
                and isinstance(translated[-1]["content"], list)
            ):
                translated[-1]["content"].append(block)
            else:
                translated.append({"role": "user", "content": [block]})
        elif role == "assistant" and message.get("tool_calls"):
            translated.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["function"]["name"],
                            "input": json.loads(call["function"]["arguments"]),
                        }
                        for call in message["tool_calls"]
                    ],
                }
            )
        else:
            translated.append({"role": role, "content": message["content"]})
    return system, cast(list[MessageParam], translated)


class AnthropicLLM:
    """Opt-in Claude client; its only output authority is the common tool schema."""

    def __init__(self, settings: Settings, sdk: AsyncAnthropic | None = None) -> None:
        if not settings.anthropic_api_key and sdk is None:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude")
        self.model = settings.claude_model
        self.sdk = sdk or AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(), timeout=15, max_retries=2
        )

    async def complete(
        self, messages: list[dict[str, Any]], schemas: list[dict[str, object]], timeout: float
    ) -> ModelReply:
        """Send masked Messages tool use and account for SDK-reported usage."""
        system, transcript = anthropic_messages(Masker().clean(messages))
        tools = cast(
            list[ToolParam],
            [
                {
                    "name": s["name"],
                    "description": s["description"],
                    "input_schema": s["parameters"],
                }
                for s in schemas
            ],
        )
        response = await self.sdk.with_options(timeout=min(timeout, 15)).messages.create(
            model=self.model,
            system=system,
            messages=transcript,
            tools=tools,
            max_tokens=2048,
            tool_choice={"type": "any"},
        )
        calls = [
            ToolCall(
                block.id,
                block.name,
                block.input if isinstance(block.input, dict) else {"_invalid_arguments": True},
            )
            for block in response.content
            if block.type == "tool_use"
        ]
        return ModelReply(calls, response.usage.input_tokens, response.usage.output_tokens)

    async def aclose(self) -> None:
        """Release the provider connection pool after a run."""
        await self.sdk.close()
