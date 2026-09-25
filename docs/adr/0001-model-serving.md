# ADR-0001 — Model serving: Qwen3.8-27B on vLLM

- **Status:** Proposed — the measurements below are empty until the scripts run on a real GPU server.
- **Milestone:** M0.2 (ROADMAP §7, Phase 0)

## Context

The harness depends on four properties of the serving stack, all unverified for Qwen3.8-27B:

1. Tool calls are parsed reliably (F3).
2. Prefix caching works for this hybrid model (Gated DeltaNet + Gated Attention), otherwise every
   agent step re-prefills the whole prefix (F2).
3. Latency and concurrency are acceptable at 8K–64K context.
4. `enable_thinking`, `reasoning_effort` and `preserve_thinking` reach the chat template (F4).

## How to measure

Start the server (adjust `--tensor-parallel-size` to the GPU count, drop `--speculative-config`
for the baseline run and add it for the MTP run):

```bash
vllm serve Qwen/Qwen3.8-27B --port 8000 --max-model-len 65536 \
  --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --enable-prefix-caching \
  --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
```

Weights: BF16 ≈ 54 GB, FP8 ≈ 27 GB, plus KV cache and activations. Then, from this repository:

```bash
uv run python -m evals.spikes.m0_2.tool_calls   --base-url http://HOST:8000/v1
uv run python -m evals.spikes.m0_2.latency      --base-url http://HOST:8000/v1
uv run python -m evals.spikes.m0_2.prefix_cache --base-url http://HOST:8000/v1
uv run python -m evals.spikes.m0_2.concurrency  --base-url http://HOST:8000/v1
uv run python -m evals.spikes.m0_2.passthrough  --base-url http://HOST:8000/v1
```

Run the set once per configuration (BF16 / FP8, with and without MTP) and paste the output here.

## Results

| Item | Measured | Threshold |
|---|---|---|
| GPU, quantisation, vLLM version | _todo_ | — |
| Tool-call parse success (50 calls) | _todo_ | ≥ 98 % |
| Truncated tool calls executed | _todo_ | 0 (enforced in M1.1) |
| TTFT at 8K / 32K / 64K | _todo_ | _decide with product_ |
| Decode tokens/s at 8K / 32K / 64K | _todo_ | _decide with product_ |
| Prefix-cache hit rate (agent-shaped) | _todo_ | > 80 % after step 1 |
| Concurrent sessions at acceptable speed | _todo_ | _decide with product_ |
| `enable_thinking=False` removes reasoning | _todo_ | yes |
| `reasoning_effort` changes token use (channel) | _todo_ | yes |
| `preserve_thinking` changes `prompt_tokens` (history key) | _todo_ | yes |
| MTP speedup (tok/s with vs without) | _todo_ | keep if ≥ 1.3× |

## Decision

_To be written after the measurements._ If the prefix-cache hit rate is low, ROADMAP §8 lists the
fallbacks: tighter compaction, shorter prefixes, or evaluating SGLang.

## Consequences

_To be written after the measurements._
