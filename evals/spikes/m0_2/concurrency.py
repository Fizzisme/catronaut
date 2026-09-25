"""M0.2 — how many concurrent sessions the server sustains.

For each concurrency level, fire that many streaming requests at once (each with its own 8K
prompt) and report per-request decode speed, TTFT and aggregate throughput. The usable number of
sessions is the highest level where per-request speed and TTFT are still acceptable; that
threshold is a product decision and goes into ADR-0001.

Run: uv run python -m evals.spikes.m0_2.concurrency --base-url http://HOST:8000/v1
"""

import argparse
import asyncio
import time

from evals.spikes.m0_2.common import add_endpoint_args, make_client, median
from evals.spikes.m0_2.latency import Sample, measure


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--context", type=int, default=8_000)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    client = make_client(args)
    print(f"{'sessions':>8} {'TTFT s (med)':>13} {'tok/s per req':>14} {'tok/s total':>12}")
    for level in args.levels:
        started = time.perf_counter()
        samples: list[Sample] = await asyncio.gather(
            *(measure(client, args.model, args.context, args.max_tokens) for _ in range(level))
        )
        elapsed = time.perf_counter() - started
        per_request = median([s.tokens_per_s for s in samples])
        print(
            f"{level:>8} {median([s.ttft for s in samples]):>13.2f} {per_request:>14.1f} "
            f"{per_request * level:>12.1f}  (wall {elapsed:.0f}s)"
        )


if __name__ == "__main__":
    asyncio.run(main())
