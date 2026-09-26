"""M0.2 — do `enable_thinking`, `reasoning_effort` and `preserve_thinking` reach the chat template?

vLLM hands `chat_template_kwargs` to the model's Jinja chat template. We cannot see the rendered
prompt, so each check looks for a change that can only happen if the switch took effect:
  1. enable_thinking=False  -> the response carries no reasoning text.
  2. reasoning_effort       -> low vs xhigh changes the number of generated tokens.
  3. preserve_thinking      -> keeping old reasoning in history changes `prompt_tokens`.

Run: uv run python -m evals.spikes.m0_2.passthrough --base-url http://HOST:8000/v1
"""

import argparse
import asyncio
from typing import Any, cast

from openai import AsyncOpenAI

from evals.spikes.m0_2.common import add_endpoint_args, make_client

PUZZLE = "A bat and a ball cost 1.10 in total. The bat costs 1.00 more than the ball. How much is the ball?"


async def ask(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, Any]],
    body: dict[str, Any],
    max_tokens: int,
) -> tuple[int, int, str]:
    """Return (prompt_tokens, completion_tokens, reasoning_text)."""
    response = await client.chat.completions.create(
        model=model, messages=cast("Any", messages), max_tokens=max_tokens, extra_body=body
    )
    message = response.choices[0].message
    reasoning = (
        getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or ""
    )
    usage = response.usage
    return (
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
        str(reasoning),
    )


async def check_enable_thinking(client: AsyncOpenAI, model: str) -> None:
    print("\n1. enable_thinking")
    messages = [{"role": "user", "content": PUZZLE}]
    for label, body in [
        ("default", {}),
        ("enable_thinking=False", {"chat_template_kwargs": {"enable_thinking": False}}),
    ]:
        _, tokens, reasoning = await ask(client, model, messages, body, 4096)
        print(f"   {label:<24} completion_tokens={tokens:<6} reasoning_chars={len(reasoning)}")
    print("   expect: default has reasoning_chars > 0, enable_thinking=False has 0")


async def check_reasoning_effort(client: AsyncOpenAI, model: str) -> None:
    print("\n2. reasoning_effort (completion tokens, lower = less thinking)")
    messages = [{"role": "user", "content": PUZZLE}]
    for channel in ("top-level", "chat_template_kwargs"):
        for effort in ("low", "medium", "xhigh"):
            body = (
                {"reasoning_effort": effort}
                if channel == "top-level"
                else {"chat_template_kwargs": {"reasoning_effort": effort}}
            )
            try:
                _, tokens, _ = await ask(client, model, messages, body, 8192)
                print(f"   {channel:<22} {effort:<7} completion_tokens={tokens}")
            except Exception as exc:  # noqa: BLE001 - a rejected channel is a valid result
                print(f"   {channel:<22} {effort:<7} REJECTED: {type(exc).__name__}: {exc}")
    print("   expect: at least one channel where low < xhigh by a clear margin")


async def check_preserve_thinking(client: AsyncOpenAI, model: str) -> None:
    print("\n3. preserve_thinking (prompt_tokens for the same history)")
    thoughts = "Let x be the ball. Then x + (x + 1.00) = 1.10, so 2x = 0.10 and x = 0.05. " * 40
    for key in ("reasoning_content", "reasoning"):
        history: list[dict[str, Any]] = [
            {"role": "user", "content": PUZZLE},
            {"role": "assistant", "content": "The ball costs 0.05.", key: thoughts},
            {"role": "user", "content": "Now double it."},
        ]
        for preserve in (True, False):
            body = {"chat_template_kwargs": {"preserve_thinking": preserve}}
            prompt_tokens, _, _ = await ask(client, model, history, body, 1)
            print(
                f"   history key {key:<18} preserve_thinking={preserve!s:<5} prompt_tokens={prompt_tokens}"
            )
    plain = [
        {"role": "user", "content": PUZZLE},
        {"role": "assistant", "content": "The ball costs 0.05."},
        {"role": "user", "content": "Now double it."},
    ]
    prompt_tokens, _, _ = await ask(client, model, plain, {}, 1)
    print(f"   history without reasoning                      prompt_tokens={prompt_tokens}")
    print("   expect: for the accepted key, preserve_thinking=True is clearly larger than False")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    args = parser.parse_args()
    client = make_client(args)
    await check_enable_thinking(client, args.model)
    await check_reasoning_effort(client, args.model)
    await check_preserve_thinking(client, args.model)


if __name__ == "__main__":
    asyncio.run(main())
