"""ReAct agent loop (M1.2): model response → tool calls → tool results, until a terminal state.

Book guide ch01 §1.1.5: every tool call in a turn is handled, and every exit is explicit, so a
caller never mistakes "produced an answer" for "completed the task".
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.llm import (
    Completion,
    LLMError,
    Message,
    StreamEvent,
    ToolCall,
    ToolResultMessage,
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

        def finish(status: RunStatus, reason: str, steps: int) -> RunFinished:
            return RunFinished(status, reason, tuple(history[start:]), steps)

        for step in range(1, max_steps + 1):
            yield StepStarted(step, max_steps)

            completion: Completion | None = None
            try:
                async for event in self._llm.stream(history, self._specs or None):
                    yield event
                    if isinstance(event, Completion):
                        completion = event
            except LLMError as exc:
                # The client already retried what could be retried
                yield finish("failed", f"model call failed: {exc}", step)
                return
            if completion is None:
                yield finish("failed", "model stream ended without a completion", step)
                return

            history.append(completion.message)
            if completion.truncated:
                yield finish("failed", "model output was cut off at max_tokens", step)
                return
            if completion.finish_reason == "other":
                yield finish("failed", "model stopped for an unexpected reason", step)
                return
            if not completion.message.tool_calls:
                yield finish("done", "", step)
                return

            # Every call gets a result before the next model request, in the order the model
            # made them, so the trajectory stays valid for the chat template
            for call in completion.message.tool_calls:
                yield ToolCallStarted(step, call)
                result = await self._execute(call)
                history.append(ToolResultMessage(tool_call_id=call.id, content=result.content))
                yield ToolCallFinished(step, call.id, result)

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
