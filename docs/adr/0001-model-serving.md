# ADR-0001 — Model serving: Qwen3.8-27B on vLLM

- **Status:** Proposed — measured 2026-09-26 on one GPU (RTX A6000); becomes Accepted when the
  owner approves it.
- **Milestone:** M0.2 (ROADMAP §7, Phase 0)

## Context

The harness depends on four properties of the serving stack, all unverified for Qwen3.8-27B when
this spike started:

1. Tool calls are parsed reliably (F3).
2. Prefix caching works for this hybrid model (Gated DeltaNet + Gated Attention); otherwise every
   agent step re-prefills the whole prefix (F2).
3. Latency and concurrency are acceptable at long context.
4. `enable_thinking`, `reasoning_effort` and `preserve_thinking` reach the chat template (F4).

## Measurement setup

| Item | Value |
|---|---|
| GPU | 1× NVIDIA RTX A6000, 48 GB (Ampere), driver 595.84 |
| Server | vLLM 0.30.0 |
| Checkpoint | `Qwen/Qwen3.8-27B-FP8` (pre-quantised, exists on the Hub). Ampere has no native FP8, so vLLM runs it weight-only (Marlin). |
| Flags | `--max-model-len 65536 --max-num-seqs 64 --gpu-memory-utilization 0.92 --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder --enable-prefix-caching --limit-mm-per-prompt '{"image":0,"video":0}'` |
| Second pass | the same plus `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` |
| Scripts | `evals/spikes/m0_2/` (`run_on_gpu.sh` runs all of them) |

The model class is `Qwen3_5ForConditionalGeneration`: Qwen3.8 reuses the Qwen3.5 architecture.

## Results

### Memory and start-up (baseline)

| Item | Measured |
|---|---|
| Weights + non-torch memory | 28.22 GiB |
| Peak activation / CUDA graphs | 2.73 GiB / 0.14 GiB |
| KV cache | **12.66 GiB = 192,238 tokens** (2.93× concurrency at 65,536 tokens) |
| Attention block size | 784 tokens (Mamba cache mode `align`, chosen by vLLM) |
| Engine start (profile, KV cache, warm-up) | 115.8 s, of which 30.9 s `torch.compile` |
| With MTP | KV cache 11.77 GiB = 162,759 tokens (2.48×), start 164.8 s |

### Checks against the thresholds

| Item | Measured | Threshold | Verdict |
|---|---|---|---|
| Tool-call parse success (50 calls) | 50/50 (100 %); right tool 50/50; 0 truncated; 0 errors | ≥ 98 % | Pass |
| Prefix-cache hit rate, agent-shaped | step 1: 0 %, steps 2–6: **99 %** (11,760 of ~11,830 tokens = 15 blocks of 784) | > 80 % after step 1 | Pass |
| `enable_thinking=False` removes reasoning | 0 reasoning characters (default: 376) | yes | Pass |
| `preserve_thinking` changes `prompt_tokens` | True 1,873 vs False 108 (no reasoning in history: 112); both history keys `reasoning_content` and `reasoning` accepted | yes | Pass |
| `reasoning_effort` changes token use | low 359 / medium 388 / xhigh 180 (top-level); 336 / 440 / 161 (`chat_template_kwargs`) | low < xhigh clearly | **Inconclusive**: one sample of an easy puzzle; the template does read the variable |
| MTP speedup | 1.34× at 11.8K-token prompt, 0.94× at 49.5K; none from 4 sessions up | ≥ 1.3× | **Fail** |

### Chat template (`chat_template.jinja`)

- Thinking is on unless `enable_thinking` is false.
- `reasoning_effort` defaults to `xhigh`; only `xhigh`, `medium`, `low` are accepted, anything
  else raises an error. The template reads it as a template variable, so
  `chat_template_kwargs` is the channel that is guaranteed to reach it.
- `preserve_thinking` defaults to **true** when undefined: old reasoning stays in the prompt unless
  the caller sets it to false.

### Latency (single stream, cold prompt)

| Prompt tokens | TTFT | Decode | With MTP: TTFT / decode |
|---|---|---|---|
| 11,802 | 10.30 s | 22.8 tok/s | 10.05 s / 30.5 tok/s |
| 49,450 | 46.94 s | 21.3 tok/s | 47.58 s / 20.1 tok/s |
| ~60K | **not measured** (probe bug: the prompt estimate was off by 1.5×, fixed afterwards); expect 55–65 s by extrapolation | | |

Prefill runs at about 1.1K tokens/s. Decode speed barely drops with context because only 16 of
64 layers keep a KV cache. Decode is capped by memory bandwidth: 651 GB/s ÷ ~27 GB of weights
≈ 24 tok/s, and 22.8 was measured.

### Concurrency (each session sends a distinct 11.8K-token prompt)

| Sessions | TTFT median | tok/s per request | tok/s total | MTP: per request / total |
|---|---|---|---|---|
| 1 | 9.3 s | 22.8 | 22.8 | 30.1 / 30.1 |
| 2 | 16.8 s | 17.3 | 34.6 | 22.0 / 44.0 |
| 4 | 25.7 s | 10.5 | 42.0 | 11.0 / 44.1 |
| 8 | 46.7 s | 5.8 | 46.1 | 5.5 / 43.9 |
| 16 | 89.5 s | 2.9 | 46.9 | 2.9 / 45.9 |

Total throughput saturates near 46 tok/s. TTFT grows with the number of sessions because prefill
is serial.

### Cost of this spike and cost per token on this card

- Instance price: **$0.634/h** (GPU + 120 GB disk, vast.ai on-demand). Credit went from $9.70 to
  $8.94: the measurement session cost **$0.76** in total, bandwidth included.
- Derived from the measurements at $0.634/h (these are calculations, not measurements):

| Load | Throughput | Cost |
|---|---|---|
| Output, 1 session | 22.8 tok/s ≈ 82K tok/h | ≈ $7.7 per 1M output tokens |
| Output, saturated (8+ sessions) | 46 tok/s ≈ 166K tok/h | ≈ $3.8 per 1M output tokens |
| Cold prefill | ~1.1K tok/s ≈ 4M tok/h | ≈ $0.16 per 1M uncached input tokens |

The GPU is paid for whether it is busy or idle, so real cost per token is higher at low use.

## Decision

1. **Serve the FP8 checkpoint with vLLM ≥ 0.30** and the flags above (F3 confirmed). Use
   `--max-num-seqs 64` or lower: vLLM's default of 256 exceeds the number of Mamba cache blocks
   (249 here) and the engine refuses to start.
2. **Keep prefix caching on** (F2 resolved for a single session). Harness rules that follow:
   - never set `preserve_thinking=false`; send the reasoning back in history (`reasoning_content`)
     so the rendered prefix is identical from one turn to the next;
   - keep the static prefix byte-stable (ROADMAP principle 4); a hit covers whole 784-token
     blocks, so at most 783 tokens are re-prefilled per step;
   - control `reasoning_effort` through `chat_template_kwargs`.
3. **Leave MTP off** by default: it helps only 1–2 sessions at short context, costs 15 % of the KV
   cache and logs a draft-model warning. Re-test on the production GPU.
4. **Vision is off in this spike.** M5.4 needs image input, so production must allow images and
   its memory must be re-measured.
5. **Do not pick the production GPU yet.** Decode speed and prefill speed scale with the GPU; the
   A6000 gives about 1–2 comfortable interactive sessions. Re-run `run_on_gpu.sh` on each
   candidate (about 30 minutes) and choose in M6.1 from the cost per token.

## Consequences

- Prefill (1.1K tok/s) and decode (22 tok/s) are the bottleneck on this card, so context size and
  prefix stability are the main cost levers for M1.6 (context engineering and compaction).
- A thinking-heavy step of 5K tokens takes about 4 minutes on this card. `reasoning_effort` per
  step and `enable_thinking=false` for simple edits are worth measuring in M2.8.
- Whether `reasoning_effort` really lowers token use is undecided; measure it on harder tasks with
  several samples in the evaluation harness (Phase 3).
- Cache hit rate under several concurrent sessions is not measured; 192K tokens of KV cache is
  shared by all sessions, so eviction is possible. Measure it in Phase 3.
- Cost per token above holds for the A6000 only; recompute it for the production GPU.

## Pitfalls met while measuring

- The vast.ai vLLM template starts its own vLLM server; `supervisorctl stop vllm` leaves the engine
  process holding VRAM. Kill the GPU processes before starting ours.
- Some hosts cannot reach `huggingface.co` (DNS). `run_on_gpu.sh` now aborts early with a message.
- The portal's reverse proxy owns port 8000; run vLLM on another port.
- The filler prompt of the latency probe is about 31 tokens per line (digits are separate tokens);
  the first version assumed 20, so the "8K", "32K" and "64K" targets were really 11.8K, 49.5K and
  over 98K tokens.

## How to re-run

```bash
git clone -b <branch> <repo> ai-service && cd ai-service
PORT=8010 nohup bash evals/spikes/m0_2/run_on_gpu.sh > run.log 2>&1 &
```
Results land in `m0_2_results/`. On vast.ai stop the template's own server first
(`supervisorctl stop vllm`, then kill the remaining engine process).
