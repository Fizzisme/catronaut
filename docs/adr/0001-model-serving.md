# ADR-0001 — Model serving: Qwen3.8-27B on vLLM

- **Status:** Accepted 2026-09-26 — measured on two GPUs (RTX A6000, RTX PRO 6000 Blackwell).
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
| GPU A | 1× NVIDIA RTX A6000, 48 GB (Ampere), 651 GB/s, driver 595.84 — $0.634/h |
| GPU B | 1× NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation, 96 GB, 1405 GB/s, driver 580.178.04 — $1.320/h |
| Server | vLLM 0.30.0 on both |
| Checkpoint | `Qwen/Qwen3.8-27B-FP8` (pre-quantised, exists on the Hub). Ampere has no native FP8, so vLLM runs it weight-only (Marlin). |
| Flags | `--max-model-len 65536 --max-num-seqs 64 --gpu-memory-utilization 0.92 --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder --enable-prefix-caching --limit-mm-per-prompt '{"image":0,"video":0}'` |
| Second pass | the same plus `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` |
| Scripts | `evals/spikes/m0_2/` (`run_on_gpu.sh` runs all of them) |

The model class is `Qwen3_5ForConditionalGeneration`: Qwen3.8 reuses the Qwen3.5 architecture.

## Results

### Memory and start-up

| Item | A6000 (48 GB) | RTX PRO 6000 (96 GB) |
|---|---|---|
| Weights + non-torch memory | 28.22 GiB | 28.09 GiB |
| Peak activation / CUDA graphs | 2.73 / 0.14 GiB | 2.90 / 0.13 GiB |
| KV cache | 12.66 GiB = **192,238 tokens** (2.93× at 64K) | 56.37 GiB = **857,793 tokens** (13.09× at 64K) |
| Attention block size | 784 tokens | 784 tokens |
| Engine start | 115.8 s (compile 30.9 s) | 101.1 s (compile 60.7 s) |
| With MTP (A6000 only) | KV cache 162,759 tokens (2.48×), start 164.8 s | not tested |

Weight memory is identical, so all extra VRAM becomes KV cache: 4.5× more sessions on the 96 GB
card. vLLM picks Mamba cache mode `align` on both.

### Checks against the thresholds

| Item | A6000 | RTX PRO 6000 | Threshold | Verdict |
|---|---|---|---|---|
| Tool-call parse success (50 calls) | 50/50, right tool 50/50 | 50/50, right tool 49/50; arguments parsed 49/50 | ≥ 98 % | Pass on both |
| Truncated tool calls | 0/50 | 0/50 | 0 | Pass |
| Prefix-cache hit rate, steps 2–6 | **99 %** (11,760 of ~11,830) | **92–94 %** (7,056 of ~7,560) | > 80 % after step 1 | Pass on both |
| `enable_thinking=False` removes reasoning | yes (376 → 0 chars) | yes (385 → 0 chars) | yes | Pass |
| `preserve_thinking` changes `prompt_tokens` | 1,873 vs 108 | 1,873 vs 108 | yes | Pass |
| `reasoning_effort` changes token use | low 359 / med 388 / **xhigh 180** | low 323 / med 278 / **xhigh 105** | low < xhigh | **Inverted, reproducibly** |
| MTP speedup | 1.34× short, 0.94× long, none ≥ 4 sessions | not tested | ≥ 1.3× | Fail |

The single tool-call miss on the RTX PRO 6000 was `"Create app/page.tsx containing a short
placeholder comment."`, where the model called a different tool from the expected `write_file`.
The call itself was well-formed, so this is a task-choice difference, not a parsing failure.

Prefix-cache percentages differ only because the probe prompt shrank after the calibration fix
(7.5K instead of 11.8K tokens): a hit always covers whole 784-token blocks, so the uncached
remainder is a bigger share of a smaller prompt. Both runs confirm caching works.

**`reasoning_effort` is inverted on both GPUs**: `xhigh` produced the *fewest* completion tokens
(105–193) and `low` the most (313–359), through both channels. Two independent runs make this
more than noise for this prompt, but it is one easy puzzle; the assumption that `low` saves
tokens does not hold and must be measured on real tasks before being used as a cost lever.

### Chat template (`chat_template.jinja`)

- Thinking is on unless `enable_thinking` is false.
- `reasoning_effort` defaults to `xhigh`; only `xhigh`, `medium`, `low` are accepted, anything
  else raises an error. The template reads it as a template variable, so
  `chat_template_kwargs` is the channel that is guaranteed to reach it.
- `preserve_thinking` defaults to **true** when undefined: old reasoning stays in the prompt unless
  the caller sets it to false.

### Latency (single stream, cold prompt)

| GPU | Prompt tokens | TTFT | Prefill | Decode |
|---|---|---|---|---|
| A6000 | 11,802 | 10.30 s | 1.15K tok/s | 22.8 tok/s |
| A6000 | 49,450 | 46.94 s | 1.05K tok/s | 21.3 tok/s |
| RTX PRO 6000 | 7,511 | **1.25 s** | 6.0K tok/s | **43.4 tok/s** |
| RTX PRO 6000 | 30,975 | **5.80 s** | 5.3K tok/s | **41.1 tok/s** |
| RTX PRO 6000 | 60,587 | **13.21 s** | 4.6K tok/s | **38.6 tok/s** |

The A6000 run used the uncalibrated probe, so its context sizes differ; prefill tok/s makes the
two comparable. **Prefill is ~4.7× faster and decode ~1.9× faster on the RTX PRO 6000.** The
decode ratio matches the memory-bandwidth ratio (1405 / 651 = 2.16×), confirming that decode is
bandwidth-bound: 22.8 and 43.4 tok/s are both ~95 % of bandwidth ÷ 27 GB of weights. Decode
barely drops with context because only 16 of 64 layers keep a KV cache.

### Concurrency (each session sends its own distinct prompt)

| Sessions | A6000: TTFT / per req / total | RTX PRO 6000: TTFT / per req / total |
|---|---|---|
| 1 | 9.3 s / 22.8 / 22.8 | 1.28 s / 42.9 / 42.9 |
| 2 | 16.8 s / 17.3 / 34.6 | 2.45 s / 39.9 / 79.9 |
| 4 | 25.7 s / 10.5 / 42.0 | 4.50 s / 36.2 / 144.9 |
| 8 | 46.7 s / 5.8 / 46.1 | 7.19 s / 26.6 / 212.7 |
| 16 | 89.5 s / 2.9 / 46.9 | 12.09 s / 16.2 / 258.6 |

This is the widest gap in the whole spike. The A6000 saturates at ~46 tok/s total no matter how
many sessions are added, and per-session speed collapses; the RTX PRO 6000 still gains throughput
at 16 sessions (258.6 tok/s, **5.5×**) while keeping 16.2 tok/s per session and a 12 s TTFT
(**7.4×** better than the A6000's 89.5 s). The 4.5× larger KV cache and the ~4.7× faster prefill
together explain it: on the A6000 the 192K-token cache and serial prefill become the wall.

### Cost

Both sessions were rented on vast.ai on-demand with a 120 GB container disk (47 GB of it used:
28 GB for the FP8 checkpoint plus the template's own model). Each measurement session cost
**$0.75–0.76** including bandwidth (A6000: $9.70 → $8.94; RTX PRO 6000: $8.96 → $8.21).

Cost per token, **calculated** from the measured throughput (not itself a measurement):

| Load | A6000 @ $0.634/h | RTX PRO 6000 @ $1.320/h |
|---|---|---|
| Output, 1 session | ≈ $7.7 / 1M | ≈ $8.5 / 1M |
| Output, 8 sessions | ≈ $3.8 / 1M | ≈ **$1.7 / 1M** |
| Output, 16 sessions | ≈ $3.8 / 1M | ≈ **$1.4 / 1M** |
| Cold prefill (uncached input) | ≈ $0.16 / 1M | ≈ **$0.07 / 1M** |

The two cards cost about the same per token for a single user, but the RTX PRO 6000 is **2.2–2.7×
cheaper under load** while also being twice as fast. The GPU is paid for whether it is busy or
idle, so real cost per token is higher than this at low use.

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
5. **Size the GPU by VRAM, not by price per hour.** Measured guidance:
   - **48 GB (A6000 class): development and CI only.** One interactive session; 3 users share
     ~46 tok/s and wait 26 s for first output.
   - **96 GB (RTX PRO 6000 class): demos and early production.** 3 users get ~36 tok/s each with a
     ~4.5 s TTFT, and there is headroom to re-enable vision. This is the default recommendation.
   - Re-run `run_on_gpu.sh` (about 10 minutes with `SKIP_MTP=1`) on any further candidate, such as
     an H100, before committing; decide in M6.1 from cost per token at the expected load.
   The cheaper card is not cheaper per unit of work: under load the 96 GB card costs less per
   token than the 48 GB one.

## Consequences

- Decode speed sets the wall-clock time of a run. A step that generates 5K tokens takes ~3.7 min
  on the A6000 and ~1.9 min on the RTX PRO 6000. Output tokens per run is therefore the number
  that decides whether the product feels usable; measure it in Phase 2.
- Context size and prefix stability remain the main cost levers for M1.6 (context engineering and
  compaction), but prefill is cheap on the 96 GB card ($0.07 per 1M tokens), so **cache misses
  hurt latency more than cost**: a miss at 60K context adds 13 s on the fast card and 55 s on the
  slow one.
- `reasoning_effort` behaves the opposite of the assumption on both GPUs, so it cannot be used as
  a cost lever yet; measure it on real tasks with several samples in Phase 3 before M2.8 relies
  on it.
- Cache hit rate with several concurrent sessions is still unmeasured. The 96 GB card holds 857K
  tokens of KV cache, enough that eviction is unlikely for a handful of sessions; the 48 GB card
  holds 192K and will evict. Measure in Phase 3.
- Vision was disabled in both runs. On the 96 GB card there is ample VRAM to turn it back on for
  M5.4; on 48 GB it would come out of an already tight KV cache.

## Pitfalls met while measuring

- The vast.ai vLLM template starts its own vLLM server and it can still be loading when the script
  begins; `supervisorctl stop vllm` leaves the engine process holding VRAM, and supervisor may
  restart the service later. Stop it, kill the leftover GPU processes, confirm `nvidia-smi` is
  near 0 MiB twice, and destroy the instance as soon as the results are copied off.
  `run_on_gpu.sh` now aborts at second 0 if more than 2 GB of VRAM is already in use.
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
