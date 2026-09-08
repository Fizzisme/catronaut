"""Tests for M1.6's OpenAI-compatible provider — the prod path.

No live server: `qwen3.8-27b` is not running anywhere (CLAUDE.md §3), so these pin the wire
shapes the model card and the OpenAI schema describe. They are deliberately concentrated on
the places this backend DIFFERS from Ollama, since anything identical is already covered by
`test_api.py` and a second copy would only pretend to add confidence.
"""

import httpx
import pytest

from app.core.exceptions import ProviderError
from app.core.model_provider.openai_compat_provider import OpenAICompatProvider


@pytest.fixture
def provider():
    return OpenAICompatProvider(
        "http://localhost:8000", "qwen3.8-27b", timeout_s=5, reasoning_effort="medium"
    )


def _reply(message: dict) -> dict:
    return {"choices": [{"message": message}], "usage": {}}


# --- response shape: choices[0].message, not message -------------------------

def test_extract_content_reads_the_first_choice(provider):
    raw = _reply({"role": "assistant", "content": "Use 16px spacing."})
    assert provider.extract_content(raw) == "Use 16px spacing."


def test_extract_content_strips_delimited_thinking(provider):
    # qwen3.8-27b emits properly delimited <think>...</think> by design, unlike qwen3:4b's
    # bare closing tag. The shared strip handles both shapes.
    raw = _reply({"content": "<think>\nWeighing options.\n</think>\n\nUse 16px spacing."})
    assert provider.extract_content(raw) == "Use 16px spacing."


def test_extract_content_rejects_an_unexpected_shape(provider):
    with pytest.raises(ProviderError):
        provider.extract_content({"no_choices": True})


def test_extract_content_points_at_the_tool_path_when_the_body_is_empty(provider):
    # A tool-calling turn has no text. Failing with a useful message beats "empty response",
    # because resolving a tool call through extract_content is the documented trap.
    raw = _reply({"content": "", "tool_calls": [{"function": {"name": "x", "arguments": "{}"}}]})
    with pytest.raises(ProviderError, match="extract_tool_calls"):
        provider.extract_content(raw)


# --- tool arguments arrive as a JSON STRING here, a dict on Ollama -----------

def test_extract_tool_calls_parses_json_string_arguments(provider):
    raw = _reply({
        "tool_calls": [
            {"function": {"name": "check_contrast", "arguments": '{"foreground": "#000000"}'}}
        ]
    })
    [call] = provider.extract_tool_calls(raw)
    assert call["name"] == "check_contrast"
    assert call["arguments"] == {"foreground": "#000000"}


def test_malformed_tool_arguments_become_an_empty_dict_not_a_crash(provider):
    # M2.2 then reports it as a bad call and gets its one repair turn; a JSONDecodeError
    # escaping the provider would instead 500 the request.
    raw = _reply({"tool_calls": [{"function": {"name": "check_contrast", "arguments": "{oops"}}]})
    [call] = provider.extract_tool_calls(raw)
    assert call["arguments"] == {}


def test_no_tool_calls_is_an_empty_list(provider):
    assert provider.extract_tool_calls(_reply({"content": "hi"})) == []


# --- usage: OpenAI field names, and no duration in the payload ---------------

def test_extract_usage_reads_openai_field_names(provider):
    raw = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        "_elapsed_s": 2.5,
    }
    usage = provider.extract_usage(raw)
    assert (usage.prompt_tokens, usage.response_tokens) == (120, 30)
    # This API returns no timing of its own, unlike Ollama's total_duration, so `chat`
    # measures it client-side and stashes it on the payload.
    assert usage.duration_s == 2.5


# --- history: reasoning must survive the round trip (M4.2) ------------------

def test_assistant_message_keeps_reasoning_and_tool_calls(provider):
    calls = [{"function": {"name": "read_file", "arguments": "{}"}}]
    raw = _reply({
        "role": "assistant",
        "content": "<think>plan</think>\n\nDone.",
        "reasoning_content": "plan",
        "tool_calls": calls,
    })
    history = provider.extract_assistant_message(raw)

    assert "<think>plan</think>" in history["content"]  # unstripped, unlike extract_content
    # Servers with a reasoning parser split thinking out instead of leaving it inline;
    # dropping it would leave `preserve_thinking` nothing to preserve.
    assert history["reasoning_content"] == "plan"
    assert history["tool_calls"] == calls


# --- request shaping ---------------------------------------------------------

def test_images_become_content_blocks_not_an_images_array(provider):
    # Agents build Ollama's shape; this API takes typed content blocks. The translation is
    # the provider's job so domain code stays backend-agnostic.
    translated = provider._as_openai_message(
        {"role": "user", "content": "Review this", "images": ["QUJD"]}
    )
    assert "images" not in translated
    assert translated["content"][0] == {"type": "text", "text": "Review this"}
    assert translated["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"


def test_an_image_url_passes_through_without_a_data_uri_wrapper(provider):
    translated = provider._as_openai_message(
        {"role": "user", "images": ["https://example.com/a.png"]}
    )
    assert translated["content"][0]["image_url"]["url"] == "https://example.com/a.png"


def test_a_message_without_images_is_untouched(provider):
    message = {"role": "assistant", "content": "hi", "tool_calls": [{"id": "1"}]}
    assert provider._as_openai_message(message) == message


def test_tool_schema_is_wrapped_in_the_function_envelope(provider):
    wrapped = provider._as_openai_tool(
        {"name": "check_contrast", "description": "d", "parameters": {"type": "object"}}
    )
    assert wrapped["type"] == "function"
    assert wrapped["function"]["name"] == "check_contrast"


def test_an_already_wrapped_tool_passes_through(provider):
    already = {"type": "function", "function": {"name": "x"}}
    assert provider._as_openai_tool(already) is already


@pytest.mark.asyncio
async def test_chat_payload_shape(provider):
    """The riskiest surface here, since no live server has ever answered this provider."""
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json=_reply({"content": "ok"}))

    provider._client = httpx.AsyncClient(
        base_url="http://localhost:8000", transport=httpx.MockTransport(handler)
    )
    raw = await provider.chat([{"role": "user", "content": "hi"}], think=False)

    assert seen["url"].endswith("/v1/chat/completions")
    body = seen["body"]
    assert body["model"] == "qwen3.8-27b"
    assert body["stream"] is False
    assert body["reasoning_effort"] == "medium"
    # Thinking is disabled through chat_template_kwargs on this API, NOT Ollama's `think`.
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "think" not in body
    # The window is a server launch flag here; sending it per request would be meaningless.
    assert "num_ctx" not in body and "options" not in body
    # `chat` measures its own elapsed time, since the payload carries no duration.
    assert "_elapsed_s" in raw


@pytest.mark.asyncio
async def test_chat_omits_thinking_switch_when_thinking_is_on(provider):
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json=_reply({"content": "ok"}))

    provider._client = httpx.AsyncClient(
        base_url="http://localhost:8000", transport=httpx.MockTransport(handler)
    )
    await provider.chat([{"role": "user", "content": "hi"}], think=True)

    # Leave the model at its own default rather than asserting it explicitly.
    assert "chat_template_kwargs" not in seen["body"]


@pytest.mark.asyncio
async def test_http_error_becomes_a_provider_error(provider):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="engine warming up")

    provider._client = httpx.AsyncClient(
        base_url="http://localhost:8000", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError, match="503"):
        await provider.chat([{"role": "user", "content": "hi"}])


def test_api_key_is_sent_as_a_bearer_header_and_absent_when_unset():
    with_key = OpenAICompatProvider("http://x", "m", timeout_s=1, api_key="secret")
    assert with_key._client.headers["authorization"] == "Bearer secret"
    without = OpenAICompatProvider("http://x", "m", timeout_s=1)
    assert "authorization" not in without._client.headers
