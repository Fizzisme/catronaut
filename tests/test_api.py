"""Smoke tests. The model backend is stubbed — real generation on qwen3:4b takes
minutes on CPU, so live model calls belong in scripts/smoke_test.py instead."""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ProviderError
from app.core.model_profile import get_model_profile
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
    # Default dev settings point at qwen3:4b -> the "small" profile.
    assert body["model_tier"] == "small"
    assert body["supports_vision"] is False


def test_analyze(client):
    response = client.post("/ui-ux/analyze", json={"prompt": "Review my login form"})
    assert response.status_code == 200
    assert response.json()["result"] == "Looks fine."


def test_analyze_with_image_on_text_only_model_still_succeeds(client):
    # qwen3:4b has no vision support (see ModelProfile), but the request must not be blocked —
    # this is a diagnostic log, not a hard gate (decided: vision stays optional/unblocking).
    response = client.post(
        "/ui-ux/analyze",
        json={"prompt": "Review this screenshot", "image_base64": "ZmFrZQ=="},
    )
    assert response.status_code == 200


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


# --- model profiles ----------------------------------------------------------

def test_profile_for_dev_model_is_small_no_vision():
    profile = get_model_profile("qwen3:4b")
    assert profile.reliability_tier == "small"
    assert profile.supports_vision is False
    assert profile.supports_native_tools is False


def test_profile_for_prod_model_is_large_with_vision():
    profile = get_model_profile("qwen3.8-27b")
    assert profile.reliability_tier == "large"
    assert profile.supports_vision is True
    assert profile.supports_native_tools is True


def test_profile_for_unknown_model_falls_back_conservatively():
    profile = get_model_profile("some-model-nobody-registered:1b")
    assert profile.reliability_tier == "small"
    assert profile.supports_vision is False
    assert profile.supports_native_tools is False
