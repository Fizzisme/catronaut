"""Helpers shared by the M0.2 model-serving spike scripts."""

import argparse
import re
import statistics
import uuid
from typing import Any

import httpx
from openai import AsyncOpenAI


def add_endpoint_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--api-key", default="EMPTY")


def make_client(args: argparse.Namespace) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=args.base_url, api_key=args.api_key, timeout=600)


def server_root(base_url: str) -> str:
    """`http://host:8000/v1` -> `http://host:8000` (where /metrics lives)."""
    return base_url.rstrip("/").removesuffix("/v1")


def make_prompt(approx_tokens: int) -> str:
    """Filler text of roughly `approx_tokens` tokens (about 20 tokens per line).

    A random tag is put first so that no earlier run can share a prefix-cache entry with it.
    Read the real size from `usage.prompt_tokens`, not from this estimate.
    """
    tag = uuid.uuid4().hex
    lines = [
        f"Record {i}: the quick brown fox number {i} jumps over lazy dog {i * 7} near gate {i % 13}."
        for i in range(max(approx_tokens // 20, 1))
    ]
    return f"[run {tag}]\n" + "\n".join(lines)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


_METRIC = re.compile(
    r"^(vllm:prefix_cache_(?:queries|hits))(?:_total)?(?:\{[^}]*\})?\s+([0-9.e+-]+)$"
)


async def prefix_cache_counters(base_url: str) -> tuple[float, float]:
    """Return (queries, hits) summed over all label sets from vLLM's /metrics."""
    async with httpx.AsyncClient(timeout=30) as http:
        text = (await http.get(f"{server_root(base_url)}/metrics")).text
    totals = {"queries": 0.0, "hits": 0.0}
    for line in text.splitlines():
        match = _METRIC.match(line)
        if match:
            totals[match.group(1).rsplit("_", 1)[1]] += float(match.group(2))
    return totals["queries"], totals["hits"]


def delta_field(delta: Any, *names: str) -> str:
    """Read the first non-empty string field among `names` from a streamed delta.

    vLLM has used both `reasoning_content` and `reasoning` for the thinking text.
    """
    for name in names:
        value = getattr(delta, name, None)
        if isinstance(value, str) and value:
            return value
    return ""
