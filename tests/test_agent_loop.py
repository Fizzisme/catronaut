import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.core.agent import (
    AgentEvent,
    AgentLimits,
    AgentLoop,
    RunFinished,
    StepStarted,
    ToolCallFinished,
    ToolCallStarted,
    ToolResult,
)
from app.core.llm import (
    AssistantMessage,
    Completion,
    ContentDelta,
    FinishReason,
    LLMUnavailableError,
    Message,
    StreamEvent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)

PROMPT = [UserMessage(content="build a landing page")]


def reply(text: str = "", *calls: ToolCall, finish: FinishReason | None = None) -> Completion:
    """A scripted model response: tool calls if any are given, otherwise a final answer."""
    reason: FinishReason = finish or ("tool_calls" if calls else "stop")
    truncated = reason == "length"
    return Completion(
        message=AssistantMessage(content=text, tool_calls=() if truncated else calls),
        finish_reason=reason,
        truncated_tool_calls=calls if truncated else (),
        usage=Usage(10, 5),
        attempts=1,
        duration_ms=1,
    )


def call(id: str, name: str = "echo", arguments: str = "{}") -> ToolCall:
    return ToolCall(id=id, name=name, arguments=arguments)


class FakeModel:
    """Replays scripted responses and records the history it was sent each time."""

    def __init__(self, *script: Completion | Exception) -> None:
        self._script = list(script)
        self.requests: list[list[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]] | None = None
    ) -> AsyncIterator[StreamEvent]:
        self.requests.append(list(messages))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if item.message.content:
            yield ContentDelta(item.message.content)
        yield item


class EchoTool:
    name = "echo"
    spec: dict[str, Any] = {"type": "function", "function": {"name": "echo", "parameters": {}}}

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, arguments: str) -> ToolResult:
        self.calls.append(arguments)
        return ToolResult(f"echo {arguments}")


class BrokenTool:
    name = "broken"
    spec: dict[str, Any] = {"type": "function", "function": {"name": "broken", "parameters": {}}}

    async def run(self, arguments: str) -> ToolResult:
        raise ValueError("disk on fire")


def run(loop: AgentLoop, messages: Sequence[Message] = PROMPT) -> list[AgentEvent]:
    async def collect() -> list[AgentEvent]:
        return [event async for event in loop.run(messages)]

    return asyncio.run(collect())


def finished(events: list[AgentEvent]) -> RunFinished:
    last = events[-1]
    assert isinstance(last, RunFinished)
    assert sum(isinstance(event, RunFinished) for event in events) == 1
    return last


def test_answer_without_tool_calls_is_done() -> None:
    model = FakeModel(reply("Here is the plan."))
    events = run(AgentLoop(model, [EchoTool()]))

    result = finished(events)
    assert result.status == "done"
    assert result.steps == 1
    assert result.messages == (AssistantMessage(content="Here is the plan."),)
    assert isinstance(events[0], StepStarted)
    assert ContentDelta("Here is the plan.") in events


def test_every_tool_call_in_a_turn_is_paired_before_the_next_request() -> None:
    echo = EchoTool()
    model = FakeModel(
        reply("", call("a", arguments='{"n": 1}'), call("b", arguments='{"n": 2}')),
        reply("All done."),
    )
    events = run(AgentLoop(model, [echo]))

    assert finished(events).status == "done"
    assert echo.calls == ['{"n": 1}', '{"n": 2}']
    # The second request ends with both results, in the order the model made the calls
    assert model.requests[1][-2:] == [
        ToolResultMessage(tool_call_id="a", content='echo {"n": 1}'),
        ToolResultMessage(tool_call_id="b", content='echo {"n": 2}'),
    ]
    started = [event.call.id for event in events if isinstance(event, ToolCallStarted)]
    results = [event.call_id for event in events if isinstance(event, ToolCallFinished)]
    assert started == results == ["a", "b"]


def test_unknown_tool_becomes_an_error_observation() -> None:
    model = FakeModel(reply("", call("a", name="Deploy")), reply("Sorry."))
    events = run(AgentLoop(model, [EchoTool()]))

    assert finished(events).status == "done"
    [result] = [event.result for event in events if isinstance(event, ToolCallFinished)]
    assert result.is_error
    assert "no tool named 'Deploy'" in result.content
    assert "echo" in result.content


def test_tool_exception_becomes_an_error_observation() -> None:
    model = FakeModel(reply("", call("a", name="broken")), reply("It failed."))
    events = run(AgentLoop(model, [BrokenTool()]))

    assert finished(events).status == "done"
    [result] = [event.result for event in events if isinstance(event, ToolCallFinished)]
    assert result.is_error
    assert "ValueError: disk on fire" in result.content


def test_step_limit_stops_the_run() -> None:
    model = FakeModel(reply("", call("a")), reply("", call("b")), reply("never requested"))
    events = run(AgentLoop(model, [EchoTool()], AgentLimits(max_steps=2)))

    result = finished(events)
    assert result.status == "stopped_at_limit"
    assert result.steps == 2
    assert len(model.requests) == 2
    # The run still ends on a paired tool result
    assert isinstance(result.messages[-1], ToolResultMessage)


def test_model_error_fails_the_run() -> None:
    model = FakeModel(LLMUnavailableError("vLLM down", attempts=4))
    result = finished(run(AgentLoop(model, [EchoTool()])))

    assert result.status == "failed"
    assert "vLLM down" in result.reason
    assert result.messages == ()


def test_truncated_output_fails_the_run_and_its_calls_are_not_executed() -> None:
    echo = EchoTool()
    model = FakeModel(reply("", call("a"), finish="length"))
    result = finished(run(AgentLoop(model, [echo])))

    assert result.status == "failed"
    assert "max_tokens" in result.reason
    assert echo.calls == []
