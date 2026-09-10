# Serving `qwen3.8-27b` with vLLM

Deployment config for the production path (ROADMAP **M1.6**). Pairs with
`MODEL_BACKEND=openai_compat`.

**Nothing here runs on a dev laptop.** The arithmetic below puts a full-context sequence at
roughly 70 GB of VRAM at bf16; the machine this was written on has 4 GB. `qwen3:4b` behind
Ollama stays the local smoke test — see CLAUDE.md §3 for why that split is deliberate.

---

## 1. Launch

```bash
export HUGGING_FACE_HUB_TOKEN=...        # only if the repo is gated
export TENSOR_PARALLEL_SIZE=2            # = number of GPUs
docker compose -f configs/vllm/docker-compose.yml up -d
docker compose -f configs/vllm/docker-compose.yml logs -f vllm
```

Then point this service at it:

```dotenv
MODEL_BACKEND=openai_compat
MODEL_NAME=qwen3.8-27b
OPENAI_BASE_URL=http://<vllm-host>:8000
# OPENAI_REASONING_EFFORT=            # unset → the model's own xhigh default
```

## 2. Verify — do this before trusting anything

```bash
python scripts/openai_compat_check.py http://<vllm-host>:8000 qwen3.8-27b
```

This is the outstanding verification M1.6's ROADMAP entry asks for. The same script already
passes 9/9 against Ollama's OpenAI-compatible endpoint, which is how the provider was proven
at all without a GPU — **and how a real bug was found** (servers disagree on the reasoning
field name). Running it here closes what Ollama could not prove, because Ollama ignores
unknown request fields rather than rejecting them:

- Is `chat_template_kwargs.enable_thinking` honoured?
- Is `reasoning_effort` accepted, and does it change anything?
- Does this engine name the reasoning field `reasoning_content` (vLLM convention) as assumed?

## 3. Two settings that must agree, and fail silently if they don't

**`--served-model-name` ↔ `MODEL_NAME` ↔ `_PROFILES` key.** `app/core/model_profile.py` is
keyed by exact tag. On a miss, `get_model_profile()` returns a conservative 4,096-token
profile and only *logs a warning* — so a 262k model would quietly run as if it were a 4k one,
and M4.1's budget would size every request against the wrong window. Keep all three as the
literal string `qwen3.8-27b`.

**`--max-model-len` ↔ `ModelProfile.context_window`.** The `openai_compat` path **cannot send
a per-request context size** — unlike Ollama's `num_ctx`, the window is fixed when the engine
starts. So M4.1's budget is a *prediction* of what this server will accept, and this launch
flag is the thing being predicted. `lifespan.py` logs the minimum it expects at startup;
compare the two on first boot.

## 4. VRAM sizing

Derived from the architecture table in
[docs/qwen3.8-27b-reference.md](../../docs/qwen3.8-27b-reference.md) — **check it against
vLLM's own startup log**, which prints the real KV-cache size once the model is loaded.

| | |
|---|---|
| Weights, bf16 | 27 B params × 2 bytes ≈ **54 GB** |
| Attention layers | **16**, not 64 — the layout is `16 × (3 × DeltaNet → FFN, 1 × Attention → FFN)`, and only the Gated Attention layers grow a KV cache |
| KV per token | 2 (K+V) × 16 layers × 4 KV heads × 256 head-dim × 2 bytes = **64 KiB** |
| KV at full 262,144 context | 64 KiB × 262,144 ≈ **16 GiB** per sequence |
| **Total, one full-context sequence** | **≈ 70 GB** |

The hybrid architecture is what keeps the KV cache small: a pure-attention 27B with 64
attention layers would need roughly four times as much.

| Hardware | Fits? |
|---|---|
| 2 × 80 GB (H100 / A100) | ✅ bf16, `--tensor-parallel-size 2` |
| 4 × 48 GB (L40S / A6000) | ✅ bf16, `--tensor-parallel-size 4` |
| 1 × 80 GB | Only with FP8 weights (~27 GB) + ~16 GB KV ≈ 43 GB |
| Anything smaller | No. Reduce `--max-model-len` first — KV scales linearly with it |

Concurrency multiplies the KV figure. `--gpu-memory-utilization` bounds the pool vLLM
pre-allocates for it; raise it for more concurrent sequences, lower it if the box shares GPUs.

## 5. Beyond 262,144 tokens (YaRN)

**Do not enable this by default.** The model card is explicit: every open-source framework
implements *static* YaRN, so the scaling factor stays constant regardless of input length and
**degrades performance on shorter texts**. Enable it only when long context is genuinely
required, and set `factor` to match your *typical* length rather than the default tuned for
1 M.

vLLM applies it as an override of the model's own rope config:

```yaml
# add to the `command:` list — factor 2.0 targets ~524,288 tokens
- --hf-overrides={"rope_parameters":{"factor":2.0,"original_max_position_embeddings":262144,"rope_type":"yarn"}}
- --max-model-len=524288
```

`rope_theta` is deliberately omitted: it comes from the model's own `config.json`, and
overriding it blindly would change the base frequency rather than just extend the window.

**If you enable YaRN, raise `ModelProfile.context_window` to the same number** — otherwise the
budgeter keeps sizing requests for 262,144 and the extra window goes unused. That number is
the one place the window is described (CLAUDE.md §3).

## 6. What is confirmed vs inferred

| Item | Status |
|---|---|
| `--max-model-len 262144` | ✅ Card: "262,144 native, extensible to 1,000,000" |
| YaRN via `rope_parameters`, static, factor-matched | ✅ Card, "Processing ultra-long texts" |
| vLLM / SGLang / TokenSpeed as the serving engines | ✅ Card, "Quickstart" |
| `--hf-overrides` YaRN syntax | ✅ vLLM docs, context-extension guide |
| `--reasoning-parser qwen3`, `--tool-call-parser qwen3_coder`, `--enable-auto-tool-choice` | ⚠️ From vLLM's documented launch for **Qwen/Qwen3.6-27B** — same family and same context length, but not this exact tag. Confirm on first boot |
| `--model Qwen/Qwen3.8-27B` | ⚠️ **Repo id not stated by the card.** It says only that weights ship in HF Transformers format. Correct this to the real id |
| VRAM figures in §4 | ⚠️ Derived from the card's architecture table, not measured. vLLM prints the real KV size at startup |
