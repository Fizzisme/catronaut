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


class ArgsBlindTool:
    """Returns the same result whatever the arguments' formatting."""

    name = "echo"
    spec: dict[str, Any] = {"type": "function", "function": {"name": "echo", "parameters": {}}}

    async def run(self, arguments: str) -> ToolResult:
        return ToolResult("ok")


class BrokenTool:
    name = "broken"
    spec: dict[str, Any] = {"type": "function", "function": {"name": "broken", "parameters": {}}}

    async def run(self, arguments: str) -> ToolResult:
        raise ValueError("disk on fire")


class PageTool:
    """Returns a new version of the page on every read, like re-reading a file after an edit."""

    name = "read"
    spec: dict[str, Any] = {"type": "function", "function": {"name": "read", "parameters": {}}}

    def __init__(self) -> None:
        self.version = 0

    async def run(self, arguments: str) -> ToolResult:
        self.version += 1
        return ToolResult(f"page.tsx v{self.version}")


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


def test_truncated_output_is_not_executed_and_the_model_is_told_to_split_it() -> None:
    echo = EchoTool()
    model = FakeModel(
        reply("Writing the page", call("a"), finish="length"),
        reply("", call("b", arguments='{"part": 1}')),
        reply("Done."),
    )
    result = finished(run(AgentLoop(model, [echo])))

    assert result.status == "done"
    assert echo.calls == ['{"part": 1}']
    # The cut-off message stays in history, followed by a notice the model reads next
    truncated, notice = model.requests[1][-2:]
    assert truncated == AssistantMessage(content="Writing the page")
    assert isinstance(notice, UserMessage)
    assert "cut off" in notice.content
    assert "'echo'" in notice.content


def test_truncated_output_too_many_times_in_a_row_fails_the_run() -> None:
    echo = EchoTool()
    model = FakeModel(
        reply("", call("a"), finish="length"),
        reply("", call("b"), finish="length"),
        reply("", call("c"), finish="length"),
        reply("never requested"),
    )
    result = finished(run(AgentLoop(model, [echo])))

    assert result.status == "failed"
    assert "max_tokens 3 times in a row" in result.reason
    assert result.steps == 3
    assert echo.calls == []


def test_a_successful_step_resets_the_failure_count() -> None:
    model = FakeModel(
        reply("", call("a"), finish="length"),
        reply("", call("b"), finish="length"),
        reply("", call("c")),
        reply("", call("d"), finish="length"),
        reply("", call("e"), finish="length"),
        reply("Done."),
    )
    result = finished(run(AgentLoop(model, [EchoTool()])))

    assert result.status == "done"


def test_same_call_with_the_same_result_three_times_fails_the_run() -> None:
    echo = EchoTool()
    model = FakeModel(
        reply("", call("a", arguments='{"path": "page.tsx"}')),
        reply("", call("b", arguments='{"path": "page.tsx"}')),
        reply("", call("c", arguments='{"path": "page.tsx"}')),
        reply("never requested"),
    )
    result = finished(run(AgentLoop(model, [echo])))

    assert result.status == "failed"
    assert "same result for the same arguments 3 times" in result.reason
    assert result.steps == 3
    assert len(model.requests) == 3
    assert isinstance(result.messages[-1], ToolResultMessage)


def test_a_repeat_below_the_limit_gets_a_note_the_model_can_act_on() -> None:
    model = FakeModel(
        reply("", call("a")),
        reply("", call("b")),
        reply("Trying something else."),
    )
    events = run(AgentLoop(model, [EchoTool()]))

    assert finished(events).status == "done"
    first, second = [
        event.result.content for event in events if isinstance(event, ToolCallFinished)
    ]
    assert first == "echo {}"
    assert second.startswith("echo {}\n\n")
    assert "already returned this exact result" in second
    # The model reads the note in the next request
    assert model.requests[2][-1] == ToolResultMessage(tool_call_id="b", content=second)


def test_same_call_with_a_new_result_is_progress() -> None:
    model = FakeModel(
        reply("", call("a", name="read")),
        reply("", call("b", name="read")),
        reply("", call("c", name="read")),
        reply("", call("d", name="read")),
        reply("Done."),
    )
    events = run(AgentLoop(model, [PageTool()]))

    assert finished(events).status == "done"
    results = [event.result.content for event in events if isinstance(event, ToolCallFinished)]
    assert not any("already returned" in content for content in results)


def test_repeats_within_one_turn_are_all_paired_before_failing() -> None:
    model = FakeModel(
        reply("", call("a"), call("b"), call("c"), call("d", arguments='{"n": 1}')),
        reply("never requested"),
    )
    result = finished(run(AgentLoop(model, [EchoTool()])))

    assert result.status == "failed"
    assert [m.tool_call_id for m in result.messages if isinstance(m, ToolResultMessage)] == [
        "a",
        "b",
        "c",
        "d",
    ]


def test_arguments_that_differ_only_in_formatting_are_the_same_call() -> None:
    model = FakeModel(
        reply("", call("a", arguments='{"path": "p", "line": 1}')),
        reply("", call("b", arguments='{"line":1,"path":"p"}')),
        reply("", call("c", arguments='{ "path": "p",  "line": 1 }')),
    )
    events = run(AgentLoop(model, [ArgsBlindTool()]))

    assert finished(events).status == "failed"
