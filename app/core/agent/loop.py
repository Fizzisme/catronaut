"""ReAct agent loop (M1.2): model response → tool calls → tool results, until a terminal state.

Book guide ch01 §1.1.5: every tool call in a turn is handled, and every exit is explicit, so a
caller never mistakes "produced an answer" for "completed the task".
"""

import asyncio
import hashlib
import json
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

from app.core.llm import (
    Completion,
    LLMError,
    Message,
    StreamEvent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

RunStatus = Literal["done", "needs_input", "stopped_at_limit", "failed", "cancelled"]


@dataclass(frozen=True)
class ToolResult:
    # What the model reads as the observation of its call
    content: str
    is_error: bool = False


class Tool(Protocol):
    """What the loop needs from a tool; the tool framework (M1.3) implements it."""

    @property
    def name(self) -> str: ...

    @property
    def spec(self) -> dict[str, Any]:
        """The OpenAI function definition sent to the model."""
        ...

    async def run(self, arguments: str) -> ToolResult:
        """Run with the raw JSON arguments the model produced."""
        ...


class ModelClient(Protocol):
    """The part of `LLMClient` the loop uses, so tests can script the model."""

    def stream(
        self, messages: Sequence[Message], tools: Sequence[dict[str, Any]] | None = None
    ) -> AsyncIterator[StreamEvent]: ...


@dataclass(frozen=True)
class AgentLimits:
    max_steps: int = 40
    # Times the same call may return the same result before the run is judged stuck
    max_repeated_calls: int = 3
    # Failed steps in a row before the run fails; a step that succeeds resets the count
    max_consecutive_failures: int = 3
    # Wall clock for the whole run. A placeholder until Phase 2 measures real runs: a step that
    # generates 5K tokens takes ~2–4 min (ADR-0001)
    max_duration_s: float = 1800.0


@dataclass(frozen=True)
class StepStarted:
    step: int
    max_steps: int


@dataclass(frozen=True)
class ToolCallStarted:
    step: int
    call: ToolCall


@dataclass(frozen=True)
class ToolCallFinished:
    step: int
    call_id: str
    result: ToolResult


@dataclass(frozen=True)
class RunFinished:
    """Always the last event of a run."""

    status: RunStatus
    # Human-readable detail for every status except `done`
    reason: str
    # Messages the run appended to the history it was given
    messages: tuple[Message, ...]
    steps: int


AgentEvent = StepStarted | StreamEvent | ToolCallStarted | ToolCallFinished | RunFinished


class AgentLoop:
    def __init__(
        self,
        llm: ModelClient,
        tools: Sequence[Tool],
        limits: AgentLimits | None = None,
    ) -> None:
        self._llm = llm
        self._tools = {tool.name: tool for tool in tools}
        self._specs = [tool.spec for tool in tools]
        self._limits = limits or AgentLimits()

    async def run(self, messages: Sequence[Message]) -> AsyncIterator[AgentEvent]:
        """Run from `messages` and stream events; the last event is always `RunFinished`."""
        history: list[Message] = list(messages)
        start = len(history)
        max_steps = self._limits.max_steps
        max_repeated = self._limits.max_repeated_calls
        # Repeats are judged on (tool, arguments, result): re-reading a file after an edit
        # returns new content and is progress, not a loop
        fingerprints: Counter[str] = Counter()
        max_failures = self._limits.max_consecutive_failures
        consecutive_failures = 0
        # One absolute deadline: the safe points check it, and every model and tool call is
        # bounded by it, so a single long call cannot run past the limit
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._limits.max_duration_s
        time_limit = f"reached the time limit ({self._limits.max_duration_s:g} s)"

        def finish(status: RunStatus, reason: str, steps: int) -> RunFinished:
            return RunFinished(status, reason, tuple(history[start:]), steps)

        for step in range(1, max_steps + 1):
            if loop.time() >= deadline:
                yield finish("stopped_at_limit", time_limit, step - 1)
                return
            yield StepStarted(step, max_steps)

            completion: Completion | None = None
            stream = self._llm.stream(history, self._specs or None)
            try:
                while True:
                    # The deadline bounds each read, never a `yield`: if it spanned a yield it
                    # could fire in the caller's code instead of here
                    event = await _before_deadline(deadline, anext(stream, None))
                    if event is None:
                        break
                    yield event
                    if isinstance(event, Completion):
                        completion = event
            except LLMError as exc:
                # The client already retried what could be retried
                yield finish("failed", f"model call failed: {exc}", step)
                return
            except _OutOfTime:
                yield finish("stopped_at_limit", time_limit, step)
                return
            if completion is None:
                yield finish("failed", "model stream ended without a completion", step)
                return

            history.append(completion.message)
            if completion.truncated:
                # Degrade and continue (ch05 §5.1.5): the cut-off calls never run (M1.1), and the
                # model is told why so it can split the work into smaller calls
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    reason = f"model output was cut off at max_tokens {max_failures} times in a row"
                    yield finish("failed", reason, step)
                    return
                history.append(UserMessage(content=_truncation_notice(completion)))
                continue
            consecutive_failures = 0
            if completion.finish_reason == "other":
                yield finish("failed", "model stopped for an unexpected reason", step)
                return
            if not completion.message.tool_calls:
                yield finish("done", "", step)
                return

            # Every call gets a result before the next model request, in the order the model
            # made them, so the trajectory stays valid for the chat template
            repeated: list[ToolCall] = []
            out_of_time = False
            for call in completion.message.tool_calls:
                if out_of_time or loop.time() >= deadline:
                    # Never started, but still paired so the history stays valid
                    out_of_time = True
                    history.append(ToolResultMessage(tool_call_id=call.id, content=_NOT_RUN))
                    continue
                yield ToolCallStarted(step, call)
                try:
                    result = await _before_deadline(deadline, self._execute(call))
                except _OutOfTime:
                    out_of_time = True
                    result = ToolResult(_INTERRUPTED, is_error=True)
                    history.append(ToolResultMessage(tool_call_id=call.id, content=result.content))
                    yield ToolCallFinished(step, call.id, result)
                    continue
                # Fingerprint the tool's own result, before any note is added to it
                fingerprint = _fingerprint(call, result)
                fingerprints[fingerprint] += 1
                count = fingerprints[fingerprint]
                if count >= max_repeated:
                    repeated.append(call)
                elif count > 1:
                    # A repeat below the limit may be legitimate (re-reading before an edit),
                    # so the model is told, not stopped, and gets a chance to change course
                    result = replace(
                        result, content=f"{result.content}\n\n{_repeat_note(max_repeated)}"
                    )
                history.append(ToolResultMessage(tool_call_id=call.id, content=result.content))
                yield ToolCallFinished(step, call.id, result)

            # Checked after the turn, so the run still ends on paired results
            if out_of_time:
                yield finish("stopped_at_limit", time_limit, step)
                return
            if repeated:
                reason = (
                    f"tool '{repeated[0].name}' returned the same result for the same arguments "
                    f"{max_repeated} times"
                )
                yield finish("failed", reason, step)
                return

        yield finish("stopped_at_limit", f"reached the step limit ({max_steps})", max_steps)

    async def _execute(self, call: ToolCall) -> ToolResult:
        """Run one call; every failure becomes an observation, never a crashed run (ch05 §5.1.5)."""
        tool = self._tools.get(call.name)
        if tool is None:
            available = ", ".join(sorted(self._tools)) or "none"
            return ToolResult(
                f"Error: there is no tool named '{call.name}'. Available tools: {available}.",
                is_error=True,
            )
        try:
            return await tool.run(call.arguments)
        except Exception as exc:
            return ToolResult(
                f"Error: tool '{call.name}' failed: {type(exc).__name__}: {exc}", is_error=True
            )


def _fingerprint(call: ToolCall, result: ToolResult) -> str:
    """Digest of a call and its result; arguments are compared as JSON, not as formatted text."""
    try:
        arguments = json.dumps(json.loads(call.arguments), sort_keys=True)
    except json.JSONDecodeError:
        arguments = call.arguments
    payload = json.dumps([call.name, arguments, result.content, result.is_error])
    return hashlib.sha256(payload.encode()).hexdigest()


class _OutOfTime(Exception):
    """The run's own deadline passed; any other TimeoutError is not ours and propagates."""


async def _before_deadline[T](deadline: float, awaitable: Awaitable[T]) -> T:
    """Await `awaitable`, cancelling it at `deadline` (event-loop time)."""
    timeout = asyncio.timeout_at(deadline)
    try:
        async with timeout:
            return await awaitable
    except TimeoutError:
        if timeout.expired():
            raise _OutOfTime from None
        raise


_INTERRUPTED = "Error: the run reached its time limit while this tool was running."
_NOT_RUN = "Error: not run; the run reached its time limit before this call started."


def _truncation_notice(completion: Completion) -> str:
    notice = "Your previous response hit the output token limit and was cut off."
    if completion.truncated_tool_calls:
        names = ", ".join(f"'{call.name}'" for call in completion.truncated_tool_calls)
        notice += f" These tool calls were incomplete and were not run: {names}."
    return (
        f"{notice} Keep each response shorter: split large content into several smaller tool calls."
    )


def _repeat_note(max_repeated: int) -> str:
    return (
        "Note: this exact call already returned this exact result earlier in the run. "
        "If you are stuck, try a different approach; the run stops once the same call "
        f"returns the same result {max_repeated} times."
    )
