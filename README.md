# Catronaut

A self-hosted AI service built around **domain-based agents**. Each agent domain is a
self-contained vertical (agent, prompts, and later its own tools and LoRA adapter) on top of a
shared core, so new domains can be added without touching core logic.

It runs **behind an existing Go API gateway**, which owns public routing, API versioning and JWT.
This service therefore exposes plain domain-relative paths (`POST /ui-ux/analyze`) with no `/api`
or `/v1` prefix, and adds no auth, CORS or rate limiting of its own.

**Status:** early. One domain is live (`ui_ux`, single-shot analysis). Tools, RAG, the agent loop,
and fine-tuning are planned — see [ROADMAP.md](ROADMAP.md).

---

## Model

Served locally through **Ollama**.

| | Development | Production (target) |
|---|---|---|
| Model | `qwen3:4b` | `qwen3.8-27b` |
| Vision | no (text-only) | yes |
| Tool calling | unreliable | reliable |

The service is model-agnostic: swap `MODEL_NAME` in `.env`, nothing else changes.
The prod tag is not in the public Ollama library, so it needs a Modelfile or a private registry on
the GPU server rather than a plain `ollama pull`.

**Known dev-model quirks** (measured, not assumed):

- **`qwen3:4b` always reasons, and `think: false` does not stop it** — it only stops Ollama from
  splitting the reasoning out. The reasoning then lands in `message.content`, terminated by a bare
  `</think>` tag with no opening tag. `OllamaProvider.extract_content` strips it.
  Measured on one prompt: `think: false` → 44s, 646 tokens, complete answer;
  `think: true` → 105s, 900 tokens of pure reasoning, cut off before answering.
  **So `MODEL_THINK=false` is the correct dev setting, not a workaround.**
- CPU-only inference is slow (~8 tok/s measured), and reasoning tokens count. A single analysis
  can take minutes; `MODEL_TIMEOUT_S` defaults to 600.
- `num_ctx` is always sent explicitly — Ollama's own default is small and truncates silently.
- Ollama's `/api/embed` is unavailable for this runner ("server does not support embeddings"),
  so RAG will need a dedicated embedding model (ROADMAP M6.3).

The provider is built **once** at FastAPI startup ([app/core/lifespan.py](app/core/lifespan.py))
and shared by every domain agent via dependency injection, so the model is never loaded twice.

## Architecture

```
Go API gateway                 public routing, versioning, JWT
  → POST /<domain>/...
    → app/api/<domain>.py        thin router, no business logic
      → app.state.orchestrator   domain registry, built once at startup
        → app/domains/<domain>/  agent: prompt assembly + post-processing
          → app/core/model_provider  ModelProvider interface → OllamaProvider
            → Ollama
```

```
catronaut/
├── app/
│   ├── main.py                  FastAPI app, /health, exception handlers
│   ├── api/                     HTTP layer — one module per domain, no version prefix
│   ├── core/
│   │   ├── config.py            pydantic-settings, single `settings` object
│   │   ├── exceptions.py        error hierarchy → HTTP status mapping
│   │   ├── lifespan.py          startup/shutdown: provider + orchestrator
│   │   ├── agent_base.py        abstract Agent
│   │   ├── orchestrator.py      resolves domain → agent instance
│   │   └── model_provider/      base.py (interface) + ollama_provider.py
│   ├── domains/
│   │   ├── registry.py          the one place a domain is declared
│   │   └── ui_ux/               agent.py, prompts.py
│   └── schemas/                 request/response models
├── models/                      base weights + per-domain LoRA adapters
├── data/                        raw / processed / vectorstore
├── evaluation/                  per-domain datasets, scripts, results
├── configs/                     Modelfiles, training configs
├── scripts/                     ingestion, training, manual smoke tests
└── tests/
```

## Adding a domain

Core is never modified:

1. Create `app/domains/<domain>/` with `agent.py` (subclass `Agent`) and `prompts.py`.
2. Register the class in [app/domains/registry.py](app/domains/registry.py).
3. Add `app/api/<domain>.py` and include it in [app/api/router.py](app/api/router.py).

Domains are `snake_case` on disk and as registry keys (`ui_ux`), `kebab-case` in URLs (`/ui-ux`).

## Tech stack

- **Framework:** FastAPI (Python 3.10+)
- **Model serving:** Ollama, over `httpx.AsyncClient`
- **Config:** pydantic-settings
- **Tests:** pytest

## Running locally

Requires [Ollama](https://ollama.com) running on the host.

```bash
ollama pull qwen3:4b
ollama serve

python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt

copy .env.example .env          # cp on Linux/macOS
uvicorn app.main:app --reload --port 8001
```

Interactive API docs: <http://localhost:8001/docs>

### Verify

```bash
curl http://localhost:8001/health
```

```json
{"status":"ok","env":"dev","model":"qwen3:4b","model_backend":"up","domains":["ui_ux"]}
```

```bash
curl -X POST http://localhost:8001/ui-ux/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Review my login form\"}"
```

Expect this to take minutes on CPU-only inference.

## Tests

```bash
pytest -q
```

The model backend is stubbed in tests; they do not call Ollama.

## Docker

Ollama runs on the host, not in the image:

```bash
docker build -t catronaut .
docker run -p 8001:8001 -e OLLAMA_BASE_URL=http://host.docker.internal:11434 catronaut
```

## Configuration

All settings come from `.env` (see [.env.example](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `dev` | `dev` also returns the raw provider payload in responses |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `MODEL_NAME` | `qwen3:4b` | Model tag (prod: `qwen3.8-27b`) |
| `MODEL_NUM_CTX` | `4096` | Context window, sent explicitly |
| `MODEL_TIMEOUT_S` | `600` | Request timeout — CPU inference is slow |
| `MODEL_THINK` | `false` | Qwen3 hybrid reasoning flag |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full milestone plan.

- [x] Service skeleton: config, model provider, orchestrator, error handling
- [x] First agent domain (`ui_ux`, single-shot)
- [ ] Tool definition + tool-call validation layer
- [ ] Context/token budgeting
- [ ] Agent loop (bounded ReAct)
- [ ] Shared RAG layer across domains
- [ ] Per-domain LoRA fine-tuning
- [ ] Second domain (`code_review`)
- [ ] Wire the gateway route through to this service in a real deployment
