"""M0.2 — TTFT and tokens/s at 8K / 32K / 64K context (median of several runs).

Run: uv run python -m evals.spikes.m0_2.latency --base-url http://HOST:8000/v1
"""

import argparse
import asyncio
import time
from dataclasses import dataclass

from openai import AsyncOpenAI

from evals.spikes.m0_2.common import (
    add_endpoint_args,
    delta_field,
    make_client,
    make_prompt,
    median,
)


@dataclass
class Sample:
    prompt_tokens: int
    ttft: float  # seconds until the first streamed token (thinking or answer)
    tokens_per_s: float  # decode speed after the first token


async def measure(client: AsyncOpenAI, model: str, context: int, max_tokens: int) -> Sample:
    started = time.perf_counter()
    first: float | None = None
    prompt_tokens = completion_tokens = 0
    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": make_prompt(context) + "\n\nSummarise the records above."}
        ],
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if chunk.usage:
            prompt_tokens, completion_tokens = (
                chunk.usage.prompt_tokens,
                chunk.usage.completion_tokens,
            )
        if chunk.choices and first is None:
            delta = chunk.choices[0].delta
            if delta.content or delta_field(delta, "reasoning_content", "reasoning"):
                first = time.perf_counter()
    ended = time.perf_counter()
    first = first or ended
    decode_time = max(ended - first, 1e-9)
    return Sample(prompt_tokens, first - started, completion_tokens / decode_time)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    # 64K would overflow --max-model-len 65536 once the 256 output tokens are added
    parser.add_argument("--contexts", type=int, nargs="+", default=[8_000, 32_000, 60_000])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    client = make_client(args)
    print(f"{'context':>8} {'prompt_tok':>11} {'TTFT s':>8} {'tok/s':>8}")
    for context in args.contexts:
        samples = [
            await measure(client, args.model, context, args.max_tokens) for _ in range(args.runs)
        ]
        print(
            f"{context:>8} {samples[-1].prompt_tokens:>11} "
            f"{median([s.ttft for s in samples]):>8.2f} {median([s.tokens_per_s for s in samples]):>8.1f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
