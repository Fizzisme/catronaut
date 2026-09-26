"""M0.2 — prefix-cache hit rate on an agent-shaped conversation (ROADMAP F2).

Each step re-sends the whole history plus one new message, exactly like an agent loop. If prefix
caching works for this hybrid model, every step after the first should hit almost all of the
tokens it shares with the previous step. Steps run one at a time so that the change in vLLM's
/metrics counters can be attributed to a single request.

Run: uv run python -m evals.spikes.m0_2.prefix_cache --base-url http://HOST:8000/v1
"""

import argparse
import asyncio
from typing import Any, cast

from evals.spikes.m0_2.common import (
    add_endpoint_args,
    make_client,
    make_prompt,
    prefix_cache_counters,
)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    parser.add_argument("--prefix-tokens", type=int, default=8_000)
    parser.add_argument("--steps", type=int, default=6)
    args = parser.parse_args()

    client = make_client(args)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": make_prompt(args.prefix_tokens)},
    ]
    print(f"{'step':>4} {'prompt_tok':>11} {'queried':>9} {'hit':>9} {'hit rate':>9}")
    total_queried = total_hit = 0.0
    for step in range(1, args.steps + 1):
        messages.append({"role": "user", "content": f"Step {step}: acknowledge with one word."})
        before_q, before_h = await prefix_cache_counters(args.base_url)
        response = await client.chat.completions.create(
            model=args.model, messages=cast("Any", messages), max_tokens=1
        )
        after_q, after_h = await prefix_cache_counters(args.base_url)
        queried, hit = after_q - before_q, after_h - before_h
        total_queried, total_hit = total_queried + queried, total_hit + hit
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        rate = hit / queried if queried else float("nan")
        print(f"{step:>4} {prompt_tokens:>11} {queried:>9.0f} {hit:>9.0f} {rate:>9.0%}")
        # A fixed assistant turn keeps the history byte-identical between steps.
        messages.append({"role": "assistant", "content": "Noted."})
    overall = total_hit / total_queried if total_queried else float("nan")
    print(f"overall hit rate: {overall:.0%}  (0% on every step => prefix caching is not working)")


if __name__ == "__main__":
    asyncio.run(main())
