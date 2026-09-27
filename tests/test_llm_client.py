import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2
import pytest

from app.core.llm import (
    AssistantMessage,
    Completion,
    ContentDelta,
    LLMClient,
    LLMConfig,
    LLMRequestError,
    LLMStreamInterrupted,
    LLMUnavailableError,
    ReasoningDelta,
    StreamEvent,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    to_wire,
)

Handler = Callable[[httpx2.Request], httpx2.Response]
PROMPT = [UserMessage(content="hi")]


def chunk(
    delta: dict[str, Any] | None = None,
    finish: str | None = None,
    usage: dict[str, int] | None = None,
) -> str:
    choices = [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": finish}]
    body: dict[str, Any] = {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "m",
        "choices": choices,
    }
    if usage:
        body["usage"] = usage
    return f"data: {json.dumps(body)}\n\n"


def sse(*chunks: str) -> httpx2.Response:
    body = "".join(chunks) + "data: [DONE]\n\n"
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, text=body)


def call_fragment(
    index: int, arguments: str, id: str | None = None, name: str | None = None
) -> dict[str, Any]:
    function: dict[str, str] = {"arguments": arguments}
    if name:
        function["name"] = name
    fragment: dict[str, Any] = {"index": index, "function": function}
    if id:
        fragment.update(id=id, type="function")
    return fragment


class Server:
    """Scripted responses, one per request; records every request body."""

    def __init__(self, *responses: httpx2.Response | Exception) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def run(
    server: Server, max_attempts: int = 4, max_tokens: int = 32_768, **kwargs: Any
) -> tuple[list[StreamEvent], list[float]]:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    config = LLMConfig(
        base_url="http://vllm/v1", model="m", max_attempts=max_attempts, max_tokens=max_tokens
    )
    client = LLMClient(
        config,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)),
        sleep=fake_sleep,
        rand=lambda: 0.5,
    )

    async def collect() -> list[StreamEvent]:
        return [event async for event in client.stream(PROMPT, **kwargs)]

    return asyncio.run(collect()), sleeps


def completion_of(events: list[StreamEvent]) -> Completion:
    last = events[-1]
    assert isinstance(last, Completion)
    return last


def test_to_wire_round_trips_reasoning_and_tool_calls() -> None:
    call = ToolCall(id="call_1", name="Read", arguments='{"path": "a.ts"}')
    wire = to_wire(
        [
            SystemMessage(content="sys"),
            UserMessage(content="go"),
            AssistantMessage(content="", reasoning="think", tool_calls=(call,)),
            ToolResultMessage(tool_call_id="call_1", content="ok"),
        ]
    )
    assert wire == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "think",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "Read", "arguments": '{"path": "a.ts"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
    ]


def test_streams_reasoning_then_content_and_assembles_completion() -> None:
    server = Server(
        sse(
            chunk({"role": "assistant", "reasoning_content": "Let me "}),
            chunk({"reasoning_content": "think."}),
            chunk({"content": "Hello"}),
            chunk({"content": " world"}, finish="stop"),
            chunk(usage={"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19}),
        )
    )
    events, sleeps = run(server)
    assert events[:4] == [
        ReasoningDelta("Let me "),
        ReasoningDelta("think."),
        ContentDelta("Hello"),
        ContentDelta(" world"),
    ]
    done = completion_of(events)
    assert done.message == AssistantMessage(content="Hello world", reasoning="Let me think.")
    assert done.finish_reason == "stop"
    assert (done.usage.prompt_tokens, done.usage.completion_tokens) == (12, 7)
    assert done.attempts == 1
    assert sleeps == []


def test_reasoning_field_used_by_newer_vllm_is_accepted() -> None:
    events, _ = run(Server(sse(chunk({"reasoning": "hmm"}), chunk({"content": "x"}, "stop"))))
    assert completion_of(events).message.reasoning == "hmm"


def test_parallel_tool_call_fragments_are_assembled_by_index() -> None:
    server = Server(
        sse(
            chunk({"tool_calls": [call_fragment(0, "", id="call_a", name="Read")]}),
            chunk({"tool_calls": [call_fragment(1, "", id="call_b", name="Glob")]}),
            chunk({"tool_calls": [call_fragment(0, '{"path": ')]}),
            chunk({"tool_calls": [call_fragment(1, '{"pattern": "*.tsx"}')]}),
            chunk({"tool_calls": [call_fragment(0, '"a.ts"}')]}),
            chunk({}, finish="tool_calls"),
        )
    )
    done = completion_of(run(server)[0])
    assert done.finish_reason == "tool_calls"
    assert done.message.tool_calls == (
        ToolCall(id="call_a", name="Read", arguments='{"path": "a.ts"}'),
        ToolCall(id="call_b", name="Glob", arguments='{"pattern": "*.tsx"}'),
    )
    assert done.truncated_tool_calls == ()


def test_truncated_tool_call_is_never_offered_for_execution() -> None:
    server = Server(
        sse(
            chunk({"tool_calls": [call_fragment(0, '{"path": "a', id="call_a", name="Write")]}),
            chunk({}, finish="length"),
        )
    )
    done = completion_of(run(server)[0])
    assert done.truncated
    assert done.message.tool_calls == ()
    assert done.truncated_tool_calls == (
        ToolCall(id="call_a", name="Write", arguments='{"path": "a'),
    )


def test_output_that_used_the_whole_budget_is_truncated_even_if_vllm_says_tool_calls() -> None:
    # vLLM 0.30 replaces finish_reason "length" with "tool_calls" (M1.1 live check, max_tokens=20)
    fragment = call_fragment(0, '{"path": "app/page.tsx\\n</', id="call_a", name="write_file")
    server = Server(
        sse(
            chunk({"tool_calls": [fragment]}),
            chunk({}, finish="tool_calls"),
            chunk(usage={"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50}),
        )
    )
    done = completion_of(run(server, max_tokens=20)[0])
    assert done.finish_reason == "length"
    assert done.message.tool_calls == ()
    assert [call.id for call in done.truncated_tool_calls] == ["call_a"]


def test_request_body_follows_adr_0001() -> None:
    server = Server(sse(chunk({"content": "x"}, "stop")))
    run(server, reasoning_effort="medium")
    body = server.bodies[0]
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["top_k"] == 20
    assert body["chat_template_kwargs"] == {"reasoning_effort": "medium"}
    assert "tools" not in body


def test_preserve_thinking_is_never_sent() -> None:
    server = Server(sse(chunk({"content": "x"}, "stop")))
    run(server, enable_thinking=False)
    assert server.bodies[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_429_is_retried_with_jittered_backoff() -> None:
    server = Server(httpx2.Response(429), sse(chunk({"content": "x"}, "stop")))
    events, sleeps = run(server)
    assert completion_of(events).attempts == 2
    assert sleeps == [0.25]  # cap 0.5 s on the first retry, scaled by rand() = 0.5


def test_connection_error_is_retried() -> None:
    server = Server(httpx2.ConnectError("reset"), sse(chunk({"content": "x"}, "stop")))
    events, _ = run(server)
    assert completion_of(events).attempts == 2


def test_persistent_5xx_gives_up_after_max_attempts() -> None:
    server = Server(*(httpx2.Response(503) for _ in range(3)))
    with pytest.raises(LLMUnavailableError) as info:
        run(server, max_attempts=3)
    assert info.value.attempts == 3
    assert len(server.bodies) == 3


def test_client_error_is_not_retried() -> None:
    server = Server(httpx2.Response(400, json={"error": {"message": "context too long"}}))
    with pytest.raises(LLMRequestError) as info:
        run(server)
    assert info.value.status_code == 400
    assert len(server.bodies) == 1


class _BreaksAfterFirstChunk(httpx2.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield chunk({"content": "partial"}).encode()
        raise httpx2.ReadError("connection reset")


def test_stream_broken_after_output_is_not_retried() -> None:
    broken = httpx2.Response(
        200, headers={"content-type": "text/event-stream"}, stream=_BreaksAfterFirstChunk()
    )
    server = Server(broken, sse(chunk({"content": "x"}, "stop")))
    with pytest.raises(LLMStreamInterrupted):
        run(server)
    assert len(server.bodies) == 1


def test_stream_without_finish_reason_is_interrupted() -> None:
    with pytest.raises(LLMStreamInterrupted):
        run(Server(sse(chunk({"content": "x"}))))
