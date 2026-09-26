#!/usr/bin/env bash
# M0.2 — run every measurement on a rented GPU box in one go, then shut the server down.
#
# Usage (on the GPU box, from the repository root):
#   bash evals/spikes/m0_2/run_on_gpu.sh
# Results land in m0_2_results/; copy that folder back, then DESTROY the instance.
#
# Knobs (environment variables):
#   MODEL=Qwen/Qwen3.8-27B   base checkpoint; "$MODEL-FP8" is tried first
#   MAX_LEN=65536            --max-model-len
#   MAX_NUM_SEQS=64          --max-num-seqs (vLLM default 256 exceeds the Mamba cache blocks of this hybrid model)
#   SKIP_MTP=1               skip the second pass with MTP speculative decoding
#   PORT=8000                vLLM port (use 8010 on vast.ai, caddy owns 8000)
#   HF_TOKEN=...             only if the model repository is gated
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen3.8-27B}"
MAX_LEN="${MAX_LEN:-65536}"
PORT="${PORT:-8000}"  # on vast.ai the portal's caddy already owns 8000: use PORT=8010
URL="http://localhost:${PORT}/v1"
OUT="m0_2_results"
mkdir -p "$OUT"
started=$(date +%s)
log() { echo "[$(( $(date +%s) - started ))s] $*" | tee -a "$OUT/timeline.txt"; }

# --- 1. Environment facts for ADR-0001 -------------------------------------------------------
{
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  python3 -c "import vllm; print('vllm', vllm.__version__)"
} > "$OUT/env.txt" 2>&1 || true
log "environment: $(tr '\n' ' ' < "$OUT/env.txt")"

# --- 1a. Fail fast when something else already holds the GPU ------------------------------------
# On vast.ai the vLLM template starts its own server (Qwen3.5-9B) and it can still be loading
# when this script starts; a stale engine also survives `supervisorctl stop vllm`.
vram_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [[ "${vram_used:-0}" -gt 2000 ]]; then
  log "ABORT: ${vram_used} MiB of VRAM is already in use, vLLM would not fit."
  log "Run: supervisorctl stop vllm; ps -eo pid,args | grep -E 'vllm serve|EngineCore' | grep -v grep | awk '{print \$1}' | xargs -r kill -9"
  log "Wait 20 s, check nvidia-smi is near 0 MiB, then rerun."
  exit 1
fi

# --- 1b. Fail fast when Hugging Face is unreachable (some hosts have broken DNS) ---------------
hf_code=$(curl -s -o /dev/null -m 15 -w "%{http_code}" https://huggingface.co || true)
if [[ "$hf_code" != "200" && "$hf_code" != "301" && "$hf_code" != "302" ]]; then
  log "ABORT: cannot reach huggingface.co (http=${hf_code}, resolves to $(getent hosts huggingface.co | cut -d' ' -f1))."
  log "This host cannot download the model. Destroy the instance and rent a different host."
  exit 1
fi

# --- 2. Pick the checkpoint: pre-quantised FP8 if it exists, else BF16 quantised on load -----
# Three outcomes: the repo exists (yes), it does not exist (no), or we could not ask (error).
fp8_status=$(python3 - "${MODEL}-FP8" <<'EOF'
import sys
from huggingface_hub import model_info
from huggingface_hub.errors import RepositoryNotFoundError

try:
    model_info(sys.argv[1])
    print("yes")
except RepositoryNotFoundError:
    print("no")
except Exception as exc:  # timeout, DNS, rate limit: not proof that the repo is missing
    print(f"error {type(exc).__name__}")
EOF
)
case "$fp8_status" in
  yes) SERVE_MODEL="${MODEL}-FP8"; QUANT_ARGS=() ;;
  no)  SERVE_MODEL="$MODEL"; QUANT_ARGS=(--quantization fp8) ;;
  *)   log "ABORT: could not check for ${MODEL}-FP8 (${fp8_status}); rerun when the network is healthy."; exit 1 ;;
esac
log "serving ${SERVE_MODEL} ${QUANT_ARGS[*]:-}"

# --- 3. Download weights and install the client tools in parallel ----------------------------
pip install -q hf_transfer 2>/dev/null || true
# Only turn on the fast downloader when it is really installed (newer huggingface_hub uses hf_xet).
if python3 -c "import hf_transfer" 2>/dev/null; then export HF_HUB_ENABLE_HF_TRANSFER=1; fi
# The Python API works on every huggingface_hub version; the `huggingface-cli` command was renamed `hf`.
( python3 -c "import sys; from huggingface_hub import snapshot_download; snapshot_download(sys.argv[1])" \
    "$SERVE_MODEL" > "$OUT/download.log" 2>&1 ) &
download_pid=$!
if ! command -v uv > /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
  export PATH="$HOME/.local/bin:$PATH"
fi
uv sync --no-default-groups --group evals -q
wait "$download_pid"
log "weights downloaded, client ready"

# --- 4. Serve, measure, stop --------------------------------------------------------------------
serve_and_measure() {
  local name=$1 scripts=$2; shift 2
  local dir="$OUT/$name"
  mkdir -p "$dir"
  log "[$name] starting vLLM"
  vllm serve "$SERVE_MODEL" --served-model-name "$MODEL" --port "$PORT" \
    --max-model-len "$MAX_LEN" --max-num-seqs "${MAX_NUM_SEQS:-64}" --gpu-memory-utilization 0.92 \
    --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder \
    --enable-prefix-caching --limit-mm-per-prompt '{"image":0,"video":0}' \
    "${QUANT_ARGS[@]}" "$@" > "$dir/server.log" 2>&1 &
  local server_pid=$!

  for _ in $(seq 1 180); do  # up to 15 minutes to load
    if curl -sf "http://localhost:${PORT}/health" > /dev/null; then break; fi
    if ! kill -0 "$server_pid" 2> /dev/null; then
      log "[$name] vLLM exited during start-up — see $dir/server.log"; tail -30 "$dir/server.log"
      return 1
    fi
    sleep 5
  done
  log "[$name] server up"
  grep -iE "KV cache|concurrency|mamba|prefix cach" "$dir/server.log" > "$dir/capacity.txt" || true

  local args=(--base-url "$URL" --model "$MODEL")
  for script in $scripts; do
    log "[$name] $script"
    uv run --no-sync python -m "evals.spikes.m0_2.$script" "${args[@]}" \
      > "$dir/$script.txt" 2>&1 || log "[$name] $script FAILED (see $dir/$script.txt)"
  done
  curl -s "http://localhost:${PORT}/metrics" > "$dir/metrics.txt" || true

  kill "$server_pid"; wait "$server_pid" 2> /dev/null || true
  log "[$name] server stopped"
}

serve_and_measure baseline "passthrough tool_calls prefix_cache latency concurrency"
if [[ "${SKIP_MTP:-0}" != "1" ]]; then
  # MTP only changes speed, so only the timing scripts are repeated.
  serve_and_measure mtp "latency concurrency" \
    --speculative-config '{"method":"mtp","num_speculative_tokens":1}' || true
fi

tar czf m0_2_results.tgz "$OUT"
log "done — copy m0_2_results.tgz back, then DESTROY the instance"
