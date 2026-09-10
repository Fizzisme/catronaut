"""Live check of M1.6's `OpenAICompatProvider` against a real OpenAI-compatible server.

Kept out of pytest for the same reason as the other `*_check.py` scripts: it needs a running
server and real generation. The unit tests pin the shapes; this proves a server actually
produces them.

**Why this can run today.** The production model, `qwen3.8-27b`, needs far more VRAM than a
laptop has, so it cannot be served locally. But M1.6 is a claim about a *protocol*, not about
a model — and **Ollama already exposes an OpenAI-compatible `/v1/chat/completions`**
alongside its native API. Pointing this provider at that endpoint exercises the entire
request/response path against a genuine implementation of the schema, with no new
infrastructure.

    python scripts/openai_compat_check.py [base_url] [model]

Defaults to the local Ollama at :11434 with `MODEL_NAME`. Point it at a vLLM or SGLang
server (`http://gpu-box:8000`) to re-run the identical checks on the real production path —
that is the outstanding verification M1.6's ROADMAP entry asks for.

What it deliberately does NOT prove, because Ollama is not the prod engine: whether
`chat_template_kwargs.enable_thinking` and `reasoning_effort` are honoured (Ollama ignores
unknown fields rather than rejecting them), and whether the prod server names its reasoning
field the same way. Re-run against vLLM to close those.
"""

import asyncio
import json
import sys
from pathlib import Path

# `python scripts/openai_compat_check.py` puts this file's own directory on sys.path,
# not the repo root — without this, `import app` fails regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.model_provider.openai_compat_provider import OpenAICompatProvider  # noqa: E402
from app.core.tools.registry import ToolRegistry  # noqa: E402
from app.domains.ui_ux.tools.accessibility import CheckContrast  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else settings.ollama_base_url
MODEL = sys.argv[2] if len(sys.argv) > 2 else settings.model_name

_PASS, _FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, _PASS if ok else _FAIL, detail))
    print(f"  [{_PASS if ok else _FAIL}] {name}" + (f" — {detail}" if detail else ""), flush=True)


async def main() -> int:
    print(f"server: {BASE_URL}  model: {MODEL}\n", flush=True)
    provider = OpenAICompatProvider(BASE_URL, MODEL, timeout_s=settings.model_timeout_s)

    try:
        print("health", flush=True)
        check("GET /v1/models answers", await provider.health())

        print("\nplain completion", flush=True)
        raw = await provider.chat(
            [{"role": "user", "content": "Reply with exactly: OK"}], max_tokens=400
        )
        message = raw["choices"][0]["message"]
        check("response has choices[0].message", isinstance(message, dict))
        check("extract_content returns text", bool(provider.extract_content(raw)),
              repr(provider.extract_content(raw))[:60])

        usage = provider.extract_usage(raw)
        check("usage uses OpenAI field names", usage.prompt_tokens > 0,
              f"{usage.prompt_tokens} prompt / {usage.response_tokens} response tokens")
        check("duration measured client-side", usage.duration_s > 0, f"{usage.duration_s:.1f}s")

        # The bug this script found on its first run: reasoning arrives under a field name
        # that is not in the OpenAI schema and differs per server, so a turn rebuilt for
        # history silently lost it. See ROADMAP M1.6 / M4.2.
        reasoning_keys = [k for k in ("reasoning_content", "reasoning") if message.get(k)]
        history = provider.extract_assistant_message(raw)
        if reasoning_keys:
            check(
                "reasoning survives into the history turn",
                any(history.get(k) for k in reasoning_keys),
                f"server names it {reasoning_keys[0]!r}",
            )
        else:
            print("  [skip] server returned no separate reasoning field", flush=True)

        print("\ntool calling", flush=True)
        registry = ToolRegistry([CheckContrast()])
        raw = await provider.chat(
            [
                {"role": "system", "content": "You must use the provided tool to answer."},
                {"role": "user", "content": "Check contrast of #777777 on #ffffff."},
            ],
            tools=registry.schema(),
            max_tokens=800,
        )
        message = raw["choices"][0]["message"]
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # A small model answering directly is a valid terminal state (ROADMAP M5.2), not
            # a protocol failure — report it rather than failing the run.
            print("  [skip] model answered without calling a tool; re-run to retry", flush=True)
        else:
            arguments = tool_calls[0]["function"]["arguments"]
            check(
                "tool arguments arrive as a JSON STRING, not a dict",
                isinstance(arguments, str),
                f"type={type(arguments).__name__}",
            )
            parsed = provider.extract_tool_calls(raw)
            check("extract_tool_calls parses them", bool(parsed) and parsed[0]["arguments"],
                  json.dumps(parsed[0], ensure_ascii=False)[:90])
            check("tool_calls round-trip into the history turn",
                  bool(provider.extract_assistant_message(raw).get("tool_calls")))
    finally:
        await provider.aclose()

    failed = [name for name, status, _ in results if status == _FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed", flush=True)
    if failed:
        print("failed: " + ", ".join(failed), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
