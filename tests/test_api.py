"""Smoke tests. The model backend is stubbed — real generation on qwen3:4b takes
minutes on CPU, so live model calls belong in scripts/smoke_test.py instead."""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ProviderError
from app.core.model_profile import get_model_profile
from app.core.model_provider.base import ModelProvider, RunUsage
from app.core.model_provider.ollama_provider import OllamaProvider
from app.domains.registry import AGENT_REGISTRY
from app.main import app


class FakeProvider(ModelProvider):
    def __init__(self, content: str = "Looks fine."):
        self._content = content

    async def chat(self, messages, *, tools=None, think=None, **options):
        return {"model": "fake", "message": {"role": "assistant", "content": self._content}}

    def extract_content(self, raw):
        return raw["message"]["content"]

    def extract_usage(self, raw):
        return RunUsage(prompt_tokens=10, response_tokens=5, duration_s=0.01)

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


def test_analyze_returns_a_run_id(client):
    body = client.post("/ui-ux/analyze", json={"prompt": "Review my login form"}).json()
    assert body["run_id"]


def test_analyze_run_id_is_unique_per_request(client):
    first = client.post("/ui-ux/analyze", json={"prompt": "Review my login form"}).json()
    second = client.post("/ui-ux/analyze", json={"prompt": "Review my login form"}).json()
    assert first["run_id"] != second["run_id"]


def test_analyze_logs_usage_metrics(client, caplog):
    with caplog.at_level("INFO"):
        client.post("/ui-ux/analyze", json={"prompt": "Review my login form"})
    done_lines = [r.message for r in caplog.records if "done" in r.message]
    assert any("prompt_tokens=10 response_tokens=5" in msg for msg in done_lines)


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


def test_assistant_message_for_history_keeps_reasoning_that_extract_content_strips():
    """The trap this method exists to close (ROADMAP M4.2).

    `extract_content` strips `<think>` — right for a response body, wrong for a history turn.
    `qwen3.8-27b` enables `preserve_thinking` by default and expects prior thinking back, so
    building history from `extract_content` would discard exactly that, and would also
    undercount the turn against M4.1's budget since the hidden part still occupies context.
    """
    provider = OllamaProvider("http://localhost:11434", "qwen3:4b", num_ctx=4096, timeout_s=5)
    raw = {"message": {"role": "assistant", "content": "Weighing options.</think>\n\nUse 16px."}}

    assert provider.extract_content(raw) == "Use 16px."  # user-facing: stripped
    history = provider.extract_assistant_message(raw)  # wire-facing: intact
    assert history["role"] == "assistant"
    assert "Weighing options." in history["content"]
    assert len(history["content"]) > len(provider.extract_content(raw))


def test_assistant_message_for_history_carries_tool_calls():
    provider = OllamaProvider("http://localhost:11434", "qwen3:4b", num_ctx=4096, timeout_s=5)
    calls = [{"function": {"name": "check_contrast", "arguments": {"foreground": "#000"}}}]
    raw = {"message": {"role": "assistant", "content": "", "tool_calls": calls}}

    history = provider.extract_assistant_message(raw)

    # A tool-calling turn must round-trip, or the loop (M5.2) cannot show the model what it
    # already asked for — and on the native path `content` is empty, so it is all there is.
    assert history["tool_calls"] == calls


def test_profiles_state_whether_history_carries_thinking():
    from app.core.model_profile import get_model_profile

    # Not a family trait: qwen3.8-27b is a different generation with `preserve_thinking` on
    # by default; qwen3:4b has no such feature. See docs/qwen3.8-27b-reference.md.
    assert get_model_profile("qwen3.8-27b").retains_thinking_in_history is True
    assert get_model_profile("qwen3:4b").retains_thinking_in_history is False


def test_reserved_output_combines_task_length_and_model_reasoning():
    """The domain owns how long the ANSWER is; the profile owns how much the model spends
    reasoning to get there (ROADMAP M5.3). One combined constant could not be right for both
    tiers: `qwen3.8-27b` reasons at `xhigh` by default and spends far more than the 4B, while
    a UI review is the same length either way."""
    from app.core.model_profile import get_model_profile
    from app.domains.ui_ux.agent import UIUXAgent

    task = UIUXAgent.reserved_output_tokens
    small = get_model_profile("qwen3:4b")
    large = get_model_profile("qwen3.8-27b")

    # Same task, different reservation — and the difference is exactly the model's own cost.
    small_total = task + small.reasoning_reserve_tokens
    large_total = task + large.reasoning_reserve_tokens
    assert large_total > small_total
    assert large_total - small_total == (
        large.reasoning_reserve_tokens - small.reasoning_reserve_tokens
    )
    # Reserving must stay a small slice of the window, not eat it.
    assert large_total < large.context_window // 4


def test_every_profile_declares_a_reasoning_reserve():
    """No default on purpose: a profile silently inheriting 0 would under-reserve on a
    thinking model, and the answer just comes back truncated."""
    from app.core.model_profile import _PROFILES

    for tag, profile in _PROFILES.items():
        assert profile.reasoning_reserve_tokens > 0, tag
        assert profile.reasoning_reserve_tokens < profile.context_window, tag


def test_every_registered_agent_declares_reserved_output_tokens():
    """`Agent.reserved_output_tokens` has no default, on purpose (ROADMAP M4.1) — what a
    response needs is a property of the task, not the framework. Forgetting it is a quiet
    failure like `Tool.read_only`: the class imports fine and only breaks at `_plan_budget`,
    so guard it here the same way the tool pack guards `read_only`."""
    for domain, agent_cls in AGENT_REGISTRY.items():
        tokens = getattr(agent_cls, "reserved_output_tokens", None)
        assert isinstance(tokens, int), f"{domain} does not declare reserved_output_tokens"
        assert tokens > 0, f"{domain} reserved a non-positive output budget"


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


# --- usage metrics (ROADMAP M1.5) -------------------------------------------

def test_extract_usage_reads_ollama_fields(provider):
    raw = {"prompt_eval_count": 12, "eval_count": 158, "total_duration": 187_769_679_300}
    usage = provider.extract_usage(raw)
    assert usage.prompt_tokens == 12
    assert usage.response_tokens == 158
    assert usage.duration_s == pytest.approx(187.77, abs=0.01)


def test_extract_usage_defaults_missing_fields_to_zero(provider):
    usage = provider.extract_usage({})
    assert usage.prompt_tokens == 0
    assert usage.response_tokens == 0
    assert usage.duration_s == 0


# --- model profiles ----------------------------------------------------------

def test_profile_for_dev_model_is_small_no_vision():
    profile = get_model_profile("qwen3:4b")
    assert profile.reliability_tier == "small"
    assert profile.supports_vision is False
    # Measured 2026-08-31 (ROADMAP M2.2): Ollama reports the `tools` capability for this
    # tag and a real call returned a well-formed `message.tool_calls`. The profile said
    # False before that was ever tested — small does not mean tool-incapable.
    assert profile.supports_native_tools is True
    assert profile.tool_call_style == "native"


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
