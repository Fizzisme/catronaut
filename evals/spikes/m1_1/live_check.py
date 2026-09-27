"""M1.1 — check the LLM client against a real vLLM server.

The unit tests replay hand-written SSE; this confirms the real server streams what they assume:
  1. reasoning    thinking and answer arrive as separate deltas; usage is reported; top_k accepted
  2. tool_call    qwen3_coder tool-call fragments assemble into one valid call
  3. round_trip   history with reasoning + tool call + tool result is accepted, and the reasoning
                  really reaches the prompt (more prompt tokens than the same history without it)
  4. truncation   finish_reason=length leaves no tool call in `message.tool_calls`

Start vLLM with the ADR-0001 flags first (port 8010 on vast.ai), then run from the repo root:
  vllm serve Qwen/Qwen3.8-27B-FP8 --served-model-name Qwen/Qwen3.8-27B --port 8010 \
    --max-model-len 65536 --max-num-seqs 64 --gpu-memory-utilization 0.92 \
    --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --enable-prefix-caching --limit-mm-per-prompt '{"image":0,"video":0}'
  uv run python -m evals.spikes.m1_1.live_check --base-url http://localhost:8010/v1
Exit code 1 when any check fails.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.llm import (
    Completion,
    LLMClient,
    LLMConfig,
    LLMError,
    Message,
    ReasoningDelta,
    ToolResultMessage,
    UserMessage,
)
from evals.spikes.m0_2.common import add_endpoint_args

if TYPE_CHECKING:
    import httpx2


def _tool(name: str, description: str, params: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": "string"} for key in params},
                "required": list(params),
            },
        },
    }


READ = _tool("read_file", "Read a text file from the workspace.", ["path"])
WRITE = _tool("write_file", "Write text content to a file in the workspace.", ["path", "content"])
PUZZLE = "A bat and a ball cost 1.10 in total. The bat costs 1.00 more than the ball. How much is the ball?"
READ_PROMPT = "Open app/page.tsx and show me what is inside."
WRITE_PROMPT = "Create app/page.tsx containing a landing page React component of at least 80 lines."
PAGE = "export default function Page() {\n  return <h1>Hello</h1>\n}\n"


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str


async def _complete(
    client: LLMClient, messages: Sequence[Message], **kwargs: Any
) -> tuple[Completion, int]:
    """Drain one stream; return the completion and the number of reasoning deltas."""
    reasoning_deltas = 0
    async for event in client.stream(messages, **kwargs):
        if isinstance(event, ReasoningDelta):
            reasoning_deltas += 1
        elif isinstance(event, Completion):
            return event, reasoning_deltas
    raise AssertionError("stream ended without a Completion")  # the client guarantees one


async def check_reasoning(client: LLMClient) -> Result:
    done, deltas = await _complete(client, [UserMessage(content=PUZZLE)])
    usage = done.usage
    ok = (
        deltas > 0
        and bool(done.message.content)
        and done.finish_reason == "stop"
        and usage.prompt_tokens > 0
        and usage.completion_tokens > 0
    )
    detail = (
        f"reasoning_deltas={deltas} reasoning_chars={len(done.message.reasoning)} "
        f"content_chars={len(done.message.content)} finish={done.finish_reason} "
        f"usage={usage.prompt_tokens}/{usage.completion_tokens} {done.duration_ms} ms"
    )
    return Result("reasoning", ok, detail)


async def check_tool_call(client: LLMClient) -> tuple[Result, Completion]:
    done, _ = await _complete(client, [UserMessage(content=READ_PROMPT)], tools=[READ, WRITE])
    calls = done.message.tool_calls
    ok = done.finish_reason == "tool_calls" and len(calls) == 1
    if ok:
        call = calls[0]
        try:
            arguments_ok = json.loads(call.arguments) == {"path": "app/page.tsx"}
        except json.JSONDecodeError:
            arguments_ok = False
        ok = bool(call.id) and call.name == "read_file" and arguments_ok
    detail = f"finish={done.finish_reason} calls={[c.model_dump() for c in calls]}"
    return Result("tool_call", ok, detail), done


async def check_round_trip(probe: LLMClient, first: Completion) -> Result:
    """`probe` has max_tokens=1: only `usage.prompt_tokens` matters here."""
    if not first.message.tool_calls or not first.message.reasoning:
        return Result("round_trip", False, "skipped: tool_call produced no call or no reasoning")

    def history(with_reasoning: bool) -> list[Message]:
        message = first.message
        if not with_reasoning:
            message = message.model_copy(update={"reasoning": ""})
        result = ToolResultMessage(tool_call_id=message.tool_calls[0].id, content=PAGE)
        return [UserMessage(content=READ_PROMPT), message, result]

    with_reasoning, _ = await _complete(probe, history(True), tools=[READ, WRITE])
    without, _ = await _complete(probe, history(False), tools=[READ, WRITE])
    ok = with_reasoning.usage.prompt_tokens > without.usage.prompt_tokens
    detail = (
        f"prompt_tokens with reasoning={with_reasoning.usage.prompt_tokens} "
        f"without={without.usage.prompt_tokens}"
    )
    return Result("round_trip", ok, detail)


async def check_truncation(short: LLMClient) -> Result:
    """Thinking off, so the tiny output budget is spent inside the tool call."""
    done, _ = await _complete(
        short, [UserMessage(content=WRITE_PROMPT)], tools=[WRITE], enable_thinking=False
    )
    if done.finish_reason != "length":
        return Result("truncation", False, f"finish={done.finish_reason}: output fit the limit")
    ok = done.message.tool_calls == ()
    partial = done.truncated_tool_calls
    how = "partial call captured" if partial else "server emitted no partial call"
    detail = f"{how}; truncated_tool_calls={[c.model_dump() for c in partial]}"
    return Result("truncation", ok, detail)


def _error(name: str, exc: LLMError) -> Result:
    return Result(name, False, f"{type(exc).__name__}: {exc}")


async def _guard(name: str, check: Awaitable[Result]) -> Result:
    """A client error fails this check only; the remaining checks still run."""
    try:
        return await check
    except LLMError as exc:
        return _error(name, exc)


async def run_checks(
    config: LLMConfig, http_client: "httpx2.AsyncClient | None" = None
) -> list[Result]:
    def client(max_tokens: int) -> LLMClient:
        return LLMClient(
            config.model_copy(update={"max_tokens": max_tokens}), http_client=http_client
        )

    full, probe, short = client(config.max_tokens), client(1), client(64)
    results = [await _guard("reasoning", check_reasoning(full))]

    first: Completion | None = None
    try:
        tool_result, first = await check_tool_call(full)
    except LLMError as exc:
        tool_result = _error("tool_call", exc)
    results.append(tool_result)

    if first is None:
        results.append(Result("round_trip", False, "skipped: tool_call raised"))
    else:
        results.append(await _guard("round_trip", check_round_trip(probe, first)))
    results.append(await _guard("truncation", check_truncation(short)))
    return results


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    args = parser.parse_args()
    config = LLMConfig(base_url=args.base_url, model=args.model, api_key=args.api_key)
    results = await run_checks(config)
    for result in results:
        print(f"{'PASS' if result.ok else 'FAIL'}  {result.name:<11} {result.detail}")
    sys.exit(0 if all(result.ok for result in results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
