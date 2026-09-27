"""Streaming LLM client for vLLM's OpenAI-compatible API (M1.1).

Rules from ADR-0001 Decision 2: reasoning goes back in history as `reasoning_content`,
`preserve_thinking` is never sent (the template keeps old reasoning, which keeps the prefix cache
warm), and `reasoning_effort` travels through `chat_template_kwargs`.
"""

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from pydantic import BaseModel, ConfigDict

from app.core.llm.errors import (
    LLMRequestError,
    LLMStreamInterrupted,
    LLMUnavailableError,
    is_retryable,
)
from app.core.llm.messages import AssistantMessage, Message, ToolCall, ToolResultMessage

if TYPE_CHECKING:
    import httpx2

FinishReason = Literal["stop", "tool_calls", "length", "other"]
ReasoningEffort = Literal["low", "medium", "xhigh"]


class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    model: str
    api_key: str = "EMPTY"
    connect_timeout: float = 5.0
    # Longest silence allowed between two chunks: the stream's liveness watchdog (ch05 §5.1.5).
    # Covers the ~55 s time to first token at 60K context on the A6000 (ADR-0001).
    read_timeout: float = 180.0
    max_tokens: int = 32_768
    # Recommended sampling for thinking mode (docs/qwen3.8-27b-reference.md)
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20
    max_attempts: int = 4
    backoff_base: float = 0.5
    backoff_max: float = 8.0


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class ReasoningDelta:
    text: str


@dataclass(frozen=True)
class ContentDelta:
    text: str


@dataclass(frozen=True)
class Completion:
    """Always the last event of a stream."""

    message: AssistantMessage
    finish_reason: FinishReason
    # Tool calls cut off by `finish_reason=length`. They are kept for the trace but never appear
    # in `message.tool_calls`, so the agent loop cannot execute them.
    truncated_tool_calls: tuple[ToolCall, ...]
    usage: Usage
    attempts: int
    duration_ms: int

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


StreamEvent = ReasoningDelta | ContentDelta | Completion


def to_wire(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Render provider-neutral messages as OpenAI chat messages for vLLM."""
    wire: list[dict[str, Any]] = []
    for message in messages:
        match message:
            case AssistantMessage():
                item: dict[str, Any] = {"role": "assistant", "content": message.content}
                if message.reasoning:
                    item["reasoning_content"] = message.reasoning
                if message.tool_calls:
                    item["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments},
                        }
                        for call in message.tool_calls
                    ]
            case ToolResultMessage():
                item = {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content,
                }
            case _:
                item = {"role": message.role, "content": message.content}
        wire.append(item)
    return wire


def _reasoning_text(delta: ChoiceDelta) -> str:
    """vLLM has used both `reasoning_content` and `reasoning` for the thinking text."""
    for name in ("reasoning_content", "reasoning"):
        value = getattr(delta, name, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _finish_reason(raw: str) -> FinishReason:
    if raw in ("stop", "tool_calls", "length"):
        return cast("FinishReason", raw)
    return "other"


@dataclass
class _PartialCall:
    id: str = ""
    name: str = ""
    arguments: list[str] = field(default_factory=lambda: [])


@dataclass
class _Accumulator:
    """Assembles one streamed response and turns chunks into delta events."""

    content: list[str] = field(default_factory=lambda: [])
    reasoning: list[str] = field(default_factory=lambda: [])
    calls: dict[int, _PartialCall] = field(default_factory=lambda: {})
    finish_reason: str | None = None
    usage: Usage = field(default_factory=Usage)

    def feed(self, chunk: ChatCompletionChunk) -> list[StreamEvent]:
        if chunk.usage:
            self.usage = Usage(chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
        events: list[StreamEvent] = []
        for choice in chunk.choices:
            delta = choice.delta
            if reasoning := _reasoning_text(delta):
                self.reasoning.append(reasoning)
                events.append(ReasoningDelta(reasoning))
            if delta.content:
                self.content.append(delta.content)
                events.append(ContentDelta(delta.content))
            # Fragments of one call share an index: id and name come first, arguments in pieces
            for fragment in delta.tool_calls or []:
                call = self.calls.setdefault(fragment.index, _PartialCall())
                if fragment.id:
                    call.id = fragment.id
                if fragment.function and fragment.function.name:
                    call.name = fragment.function.name
                if fragment.function and fragment.function.arguments:
                    call.arguments.append(fragment.function.arguments)
            if choice.finish_reason:
                self.finish_reason = choice.finish_reason
        return events

    def completion(self, finish_reason: str, attempts: int, duration_ms: int) -> Completion:
        finish = _finish_reason(finish_reason)
        calls = tuple(
            ToolCall(id=call.id, name=call.name, arguments="".join(call.arguments))
            for _, call in sorted(self.calls.items())
        )
        truncated = finish == "length"
        message = AssistantMessage(
            content="".join(self.content),
            reasoning="".join(self.reasoning),
            tool_calls=() if truncated else calls,
        )
        return Completion(
            message=message,
            finish_reason=finish,
            truncated_tool_calls=calls if truncated else (),
            usage=self.usage,
            attempts=attempts,
            duration_ms=duration_ms,
        )


class LLMClient:
    def __init__(
        self,
        config: LLMConfig,
        *,
        http_client: "httpx2.AsyncClient | None" = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._config = config
        self._sleep = sleep
        self._rand = rand
        # The SDK's own retries are off: it also retries 408/409, and we count attempts ourselves
        self._client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            max_retries=0,
            timeout=openai.Timeout(config.read_timeout, connect=config.connect_timeout),
            http_client=http_client,
        )

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] | None = None,
        *,
        reasoning_effort: ReasoningEffort | None = None,
        enable_thinking: bool | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream one model response: delta events, then a `Completion`.

        Retryable failures are retried with backoff and jitter only while no event has been
        delivered; after that a failure raises `LLMStreamInterrupted`.
        """
        template_kwargs: dict[str, Any] = {}
        if reasoning_effort is not None:
            template_kwargs["reasoning_effort"] = reasoning_effort
        if enable_thinking is not None:
            template_kwargs["enable_thinking"] = enable_thinking
        extra_body: dict[str, Any] = {"top_k": self._config.top_k}
        if template_kwargs:
            extra_body["chat_template_kwargs"] = template_kwargs

        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            state = _Accumulator()
            delivered = False
            try:
                chunks = await self._client.chat.completions.create(
                    model=self._config.model,
                    messages=cast("Any", to_wire(messages)),
                    tools=cast("Any", list(tools)) if tools else openai.omit,
                    stream=True,
                    stream_options={"include_usage": True},
                    max_tokens=self._config.max_tokens,
                    temperature=self._config.temperature,
                    top_p=self._config.top_p,
                    extra_body=extra_body,
                )
                try:
                    async for chunk in chunks:
                        for event in state.feed(chunk):
                            delivered = True
                            yield event
                finally:
                    await chunks.close()
            except openai.APIError as exc:
                if delivered:
                    raise LLMStreamInterrupted(f"stream broke after output: {exc}") from exc
                if not is_retryable(exc):
                    status = exc.status_code if isinstance(exc, openai.APIStatusError) else None
                    raise LLMRequestError(str(exc), status_code=status) from exc
                if attempt >= self._config.max_attempts:
                    raise LLMUnavailableError(
                        f"gave up after {attempt} attempts: {exc}", attempts=attempt
                    ) from exc
                await self._sleep(self._backoff(attempt))
                continue

            if state.finish_reason is None:
                raise LLMStreamInterrupted("stream ended without a finish_reason")
            duration_ms = round((time.monotonic() - started) * 1000)
            yield state.completion(state.finish_reason, attempt, duration_ms)
            return

    def _backoff(self, attempt: int) -> float:
        """Full jitter: a uniform delay up to an exponentially growing cap."""
        cap = min(self._config.backoff_max, self._config.backoff_base * 2 ** (attempt - 1))
        return cap * self._rand()
