import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.agent.llm.anthropic_client import AnthropicLLM
from backend.app.agent.llm.factory import create_client
from backend.app.agent.llm.openai_compat import OpenAICompatLLM
from backend.app.config import Settings


def test_environment_keys_are_redacted_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "API_KEY": "synthetic-mutation-key",
        "ANTHROPIC_API_KEY": "synthetic-anthropic-key",
        "MIMO_API_KEY": "synthetic-mimo-key",
        "DATABASE_URL": "postgresql://demo:synthetic-db-password@localhost/clearline",
        "AGENT_DATABASE_URL": "postgresql://agent:synthetic-agent-password@localhost/clearline",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = Settings()
    for value in values.values():
        assert value not in str(settings)
        assert value not in repr(settings)
        assert value not in settings.model_dump_json()
    assert settings.api_key.get_secret_value() == values["API_KEY"]
    assert settings.anthropic_api_key.get_secret_value() == values["ANTHROPIC_API_KEY"]
    assert settings.mimo_api_key.get_secret_value() == values["MIMO_API_KEY"]


def test_empty_mutation_key_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "")
    with pytest.raises(ValidationError, match="api_key"):
        Settings()


@pytest.mark.parametrize("provider", ["claude", "mimo"])
def test_live_sdk_receives_the_explicitly_unwrapped_key(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-anthropic-key")
    monkeypatch.setenv("MIMO_API_KEY", "synthetic-mimo-key")
    monkeypatch.setenv("MIMO_BASE_URL", "https://provider.example.invalid/v1")
    monkeypatch.setenv("MIMO_MODEL", "fixture-model")
    client = create_client(Settings())
    try:
        assert isinstance(client, AnthropicLLM | OpenAICompatLLM)
        expected = "synthetic-anthropic-key" if provider == "claude" else "synthetic-mimo-key"
        assert client.sdk.api_key == expected
    finally:
        asyncio.run(client.aclose())


@pytest.mark.parametrize("key", [b"", b"incorrect-key", b"\xff"])
def test_invalid_mutation_key_returns_unauthorized(client: TestClient, key: bytes) -> None:
    response = client.post(
        "/ingest/bank-lines",
        headers={b"X-API-Key": key},
        files={"file": ("bank.csv", b"invalid csv")},
    )
    assert response.status_code == 401
