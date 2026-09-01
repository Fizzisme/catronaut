"""Manual M2.2 check: the real resolver against a real model.

Kept out of pytest for the usual reason — each scenario is a real generation and takes
20–80s on the dev CPU box. The pytest suite covers the same logic with stubs; this proves
the model actually cooperates.

    python scripts/tool_call_check.py [model_name]

Expects: ToolCall, ToolCall, NoToolCall. A NoToolCall in the first two slots means the
model declined to call the tool — that is a model/prompt problem, not a parser bug.
"""

import asyncio
import sys
from pathlib import Path

# `python scripts/tool_call_check.py` puts this file's own directory on sys.path,
# not the repo root — without this, `import app` fails regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel

from app.core.config import settings
from app.core.model_profile import get_model_profile
from app.core.model_provider.ollama_provider import OllamaProvider
from app.core.run_context import RunContext
from app.core.tools.base import Tool
from app.core.tools.parsing import NoToolCall, ToolCall, ToolCallFailure, build_tool_instructions
from app.core.tools.registry import ToolRegistry
from app.core.tools.resolver import ToolCallResolver

MODEL = sys.argv[1] if len(sys.argv) > 1 else settings.model_name

NEEDS_TOOL = (
    "My submit button uses #999999 text on a #ffffff background. "
    "Check whether that passes accessibility contrast requirements."
)
NEEDS_NO_TOOL = "In one sentence, what is visual hierarchy in UI design?"


class ContrastArgs(BaseModel):
    foreground: str
    background: str


class CheckContrast(Tool):
    """Stand-in for the real M2.4 tool — this script tests the plumbing, not the tool."""

    name = "check_contrast"
    description = "Check the WCAG contrast ratio between two hex colors."
    args_schema = ContrastArgs
    read_only = True

    async def run(self, args: ContrastArgs) -> str:
        return f"{args.foreground} on {args.background}"


async def scenario(provider, registry, style, prompt, label) -> str:
    resolver = ToolCallResolver(provider, registry, style=style)
    run = RunContext(domain="ui_ux", model_profile=get_model_profile(MODEL))

    messages = []
    if style == "prompt":
        messages.append({"role": "system", "content": build_tool_instructions(registry)})
    messages.append({"role": "user", "content": prompt})

    raw = await provider.chat(
        messages=messages,
        tools=registry.schema() if style == "native" else None,
    )
    result = await resolver.resolve(run, messages, raw)

    if isinstance(result, ToolCall):
        detail = f"{result.name}({result.raw_args})"
    elif isinstance(result, NoToolCall):
        detail = result.content[:160]
    elif isinstance(result, ToolCallFailure):
        detail = result.reason
    else:
        detail = repr(result)

    usage = provider.extract_usage(raw)
    print(
        f"\n[{label}] {type(result).__name__}\n  {detail}\n"
        f"  {usage.duration_s:.1f}s, {usage.response_tokens} response tokens",
        flush=True,
    )
    return type(result).__name__


async def main() -> int:
    print(f"model: {MODEL} (this takes a few minutes on CPU)", flush=True)
    provider = OllamaProvider(
        settings.ollama_base_url,
        MODEL,
        num_ctx=settings.model_num_ctx,
        timeout_s=settings.model_timeout_s,
        think=settings.model_think,
    )
    registry = ToolRegistry([CheckContrast()])
    try:
        results = [
            await scenario(provider, registry, "native", NEEDS_TOOL, "native / needs tool"),
            await scenario(provider, registry, "prompt", NEEDS_TOOL, "prompt / needs tool"),
            await scenario(provider, registry, "native", NEEDS_NO_TOOL, "native / no tool needed"),
        ]
    finally:
        await provider.aclose()

    expected = ["ToolCall", "ToolCall", "NoToolCall"]
    print(f"\nresults={results}\nexpected={expected}", flush=True)
    if results != expected:
        print("MISMATCH")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
