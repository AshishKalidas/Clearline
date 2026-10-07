import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from backend.app.agent.llm.anthropic_client import AnthropicLLM, anthropic_messages
from backend.app.agent.llm.factory import client_scope, create_client
from backend.app.agent.llm.openai_compat import OpenAICompatLLM, parse_arguments
from backend.app.agent.schemas import tool_schemas
from backend.app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
RAW = ["9999999999999", "88888888", "fictional@example.invalid", "+27 00 000 0000"]


@pytest.mark.parametrize("provider", ["claude", "mimo"])
def test_real_sdk_recorded_response_privacy_retries_usage(provider: str) -> None:
    requests: list[httpx.Request] = []
    payload = json.loads((FIXTURES / f"{provider}_tool_response.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert all(raw not in request.content.decode() for raw in RAW)
        body = json.loads(request.content)
        assert body["model"] == "fixture-configured-model"
        assert body["tools"]
        assert request.extensions["timeout"]["read"] <= 7
        if len(requests) == 1:
            return httpx.Response(
                500, json={"error": {"type": "server_error", "message": "Synthetic retry"}}
            )
        return httpx.Response(200, json=payload)

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        settings = Settings(
            claude_model="fixture-configured-model", mimo_model="fixture-configured-model"
        )
        if provider == "claude":
            sdk = AsyncAnthropic(api_key="offline-fixture", http_client=http, max_retries=2)
            client = AnthropicLLM(settings, sdk=sdk)
        else:
            sdk = AsyncOpenAI(api_key="offline-fixture", http_client=http, max_retries=2)
            client = OpenAICompatLLM(settings, sdk=sdk)
        response = await client.complete(
            [
                {"role": "system", "content": "Read-only investigation."},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"untrusted_bank_text": " ".join(RAW), "amount_cents": 123456789}
                    ),
                },
            ],
            tool_schemas(),
            timeout=7,
        )
        assert response.prompt_tokens == 120 and response.completion_tokens == 34
        assert response.calls[0].name == "submit_proposal"
        assert response.calls[0].arguments["decision"] == "escalate"
        assert len(requests) == 2
        await client.aclose()
        assert http.is_closed

    asyncio.run(run())


def test_provider_envelopes_and_malformed_arguments() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "Policy"},
        {"role": "user", "content": "Investigate"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "a",
                    "function": {"name": "find_customers", "arguments": '{"name_query":"Lumen"}'},
                },
                {
                    "id": "b",
                    "function": {"name": "search_runbook", "arguments": '{"query":"split"}'},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "a", "name": "find_customers", "content": "[]"},
        {
            "role": "tool",
            "tool_call_id": "b",
            "name": "search_runbook",
            "content": '{"error":"missing"}',
        },
    ]
    system, translated = anthropic_messages(messages)
    assert system == "Policy"
    assert len(translated) == 3
    assert translated[-1]["content"][1]["is_error"]
    assert parse_arguments("broken") == {"_invalid_arguments": True}
    assert parse_arguments("[]") == {"_invalid_arguments": True}
    assert parse_arguments('{"k":5}') == {"k": 5}


def test_configuration_is_opt_in() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        create_client(Settings(llm_provider="claude", anthropic_api_key=""))
    with pytest.raises(ValueError, match="MIMO_MODEL"):
        create_client(Settings(llm_provider="mimo", mimo_model=""))
    with pytest.raises(ValueError, match="MIMO_API_KEY"):
        create_client(
            Settings(llm_provider="mimo", mimo_model="fixture", mimo_api_key="", mimo_base_url="")
        )

    async def run() -> None:
        async with client_scope(Settings(llm_provider="stub")) as client:
            assert client.model == "stub-baseline-v1"

    asyncio.run(run())
