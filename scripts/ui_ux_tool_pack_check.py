"""Manual M2.4 check: the real ui_ux tool pack (all 4 tools registered together)
against a real model, including one real network fetch.

Kept out of pytest for the usual reasons: real generation is slow, and this also makes
one live HTTP request to http://example.com/ — IANA's domain reserved for
documentation/testing (see RFC 2606), so it's safe to depend on in a script.

    python scripts/ui_ux_tool_pack_check.py [model_name]

This is also the measurement M2.2 flagged as missing: selection accuracy was only
verified with ONE tool registered. With all 4 registered, does the model still pick
the right one per prompt?
"""

import asyncio
import sys
from pathlib import Path

# `python scripts/ui_ux_tool_pack_check.py` puts this file's own directory on
# sys.path, not the repo root — without this, `import app` fails regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.model_profile import get_model_profile
from app.core.model_provider.ollama_provider import OllamaProvider
from app.core.run_context import RunContext
from app.core.tools.parsing import NoToolCall, ToolCall, ToolCallFailure, build_tool_instructions
from app.core.tools.registry import ToolRegistry
from app.core.tools.resolver import ToolCallResolver
from app.domains.ui_ux.tools import TOOLS

MODEL = sys.argv[1] if len(sys.argv) > 1 else settings.model_name

SCENARIOS = [
    (
        "expects check_contrast",
        "My submit button uses #999999 text on a #ffffff background. "
        "Check whether that passes accessibility contrast requirements.",
        "check_contrast",
    ),
    (
        "expects lookup_heuristic",
        "What does the 'error prevention' usability heuristic mean? Look it up.",
        "lookup_heuristic",
    ),
    (
        "expects fetch_docs",
        "Fetch http://example.com/ and tell me what it says.",
        "fetch_docs",
    ),
    (
        "expects no tool call",
        "In one sentence, what is visual hierarchy in UI design?",
        None,
    ),
]


async def run_scenario(provider, registry, label, prompt, expected_tool) -> bool:
    resolver = ToolCallResolver(provider, registry, style="native")
    run = RunContext(domain="ui_ux", model_profile=get_model_profile(MODEL))

    messages = [{"role": "user", "content": prompt}]
    raw = await provider.chat(messages=messages, tools=registry.schema())
    result = await resolver.resolve(run, messages, raw)

    if isinstance(result, ToolCall):
        got = result.name
        ok = got == expected_tool
        print(f"\n[{label}] called {got!r} args={result.raw_args} -> {'OK' if ok else 'WRONG TOOL'}")
    elif isinstance(result, NoToolCall):
        got = None
        ok = expected_tool is None
        print(f"\n[{label}] no tool call, answered: {result.content[:120]!r} -> {'OK' if ok else 'EXPECTED A CALL'}")
    else:
        assert isinstance(result, ToolCallFailure)
        got = "FAILURE"
        ok = False
        print(f"\n[{label}] tool call failed: {result.reason} -> WRONG")

    usage = provider.extract_usage(raw)
    print(f"  {usage.duration_s:.1f}s, {usage.response_tokens} response tokens")
    return ok


async def main() -> int:
    print(f"model: {MODEL}, {len(TOOLS)} tools registered (this takes a few minutes on CPU)")
    provider = OllamaProvider(
        settings.ollama_base_url,
        MODEL,
        num_ctx=settings.model_num_ctx,
        timeout_s=settings.model_timeout_s,
        think=settings.model_think,
    )
    registry = ToolRegistry(TOOLS)
    try:
        results = [
            await run_scenario(provider, registry, label, prompt, expected)
            for label, prompt, expected in SCENARIOS
        ]
    finally:
        await provider.aclose()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} scenarios picked the right tool (or correctly picked none).")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
