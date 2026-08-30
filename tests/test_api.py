"""Smoke tests. The model backend is stubbed — real generation on qwen3:4b takes
minutes on CPU, so live model calls belong in scripts/smoke_test.py instead."""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ProviderError
from app.core.model_provider.base import ModelProvider
from app.core.model_provider.ollama_provider import OllamaProvider
from app.main import app


class FakeProvider(ModelProvider):
    def __init__(self, content: str = "Looks fine."):
        self._content = content

    async def chat(self, messages, *, tools=None, think=None, **options):
        return {"model": "fake", "message": {"role": "assistant", "content": self._content}}

    def extract_content(self, raw):
        return raw["message"]["content"]

    async def health(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client():
    with TestClient(app) as c:
        provider = FakeProvider()
        c.app.state.model_provider = provider
        for agent in c.app.state.orchestrator._agents.values():
            agent.model_provider = provider
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "ui_ux" in body["domains"]


def test_analyze(client):
    response = client.post("/ui-ux/analyze", json={"prompt": "Review my login form"})
    assert response.status_code == 200
    assert response.json()["result"] == "Looks fine."


def test_analyze_rejects_empty_prompt(client):
    assert client.post("/ui-ux/analyze", json={"prompt": ""}).status_code == 422


def test_unknown_domain_is_404(client):
    from app.core.exceptions import UnknownDomainError

    with pytest.raises(UnknownDomainError):
        client.app.state.orchestrator.get_agent("nope")


# --- provider response normalization ---------------------------------------
# qwen3:4b ignores `think: false` and leaks its reasoning into message.content,
# terminated by a bare closing tag. Regression-guard that behaviour.

@pytest.fixture
def provider():
    return OllamaProvider("http://localhost:11434", "qwen3:4b", num_ctx=4096, timeout_s=5)


def test_extract_content_strips_leaked_reasoning(provider):
    raw = {"message": {"content": "Let me think about it.</think>\n\nUse 16px spacing."}}
    assert provider.extract_content(raw) == "Use 16px spacing."


def test_extract_content_passes_clean_output_through(provider):
    assert provider.extract_content({"message": {"content": "Use 16px spacing."}}) == "Use 16px spacing."


def test_extract_content_rejects_empty(provider):
    with pytest.raises(ProviderError):
        provider.extract_content({"message": {"content": "   "}})


def test_extract_content_rejects_bad_shape(provider):
    with pytest.raises(ProviderError):
        provider.extract_content({"error": "boom"})
