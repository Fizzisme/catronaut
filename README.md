# Catrounaut

A self-hosted AI service built for extensible, domain-based agents. Designed domain-driven from day one, so new agent domains can be added without touching core logic.

## Model

**Qwen3.8-27B** — self-hosted, served via Ollama.

Why this model:
- Dense multimodal model (hybrid attention: linear attention across most layers, full attention interleaved) with a built-in vision tower — handles both image and text input
- Ships with the `qwen3_coder` tool-call parser, well suited for agentic / tool-use workflows
- Native 262K token context, extensible up to ~1M via YaRN if needed
- Multi-token prediction (MTP) head for lower decode latency
- Shares its backbone with Qwen3.5-27B, which scores IFEval 95.0 and ~72.4% on SWE-bench Verified — strong on both software engineering and OCR/spatial reasoning tasks

The model is loaded once at FastAPI startup (`app/core/lifespan.py`) and shared across all domain agents via dependency injection, avoiding redundant VRAM usage.

## Architecture

Domain-driven: each agent domain owns its own logic (agent, prompts, tools, skills, schema), isolated from shared core (model provider, orchestrator, memory/RAG). Adding a new domain means adding one folder under `app/domains/` and one router under `app/api/v1/` — no changes to core.

```
catrounaut/
├── app/
│   ├── api/                # HTTP layer (FastAPI routers)
│   ├── core/                # model provider, orchestrator, memory, config, lifespan
│   ├── domains/
│   │   └── <domain>/        # agent, prompts, tools, skills — self-contained per domain
│   ├── schemas/
│   └── main.py
├── models/                  # weights/adapter config (per-domain LoRA)
├── data/                    # raw / processed / vectorstore
├── evaluation/               # per-domain datasets + eval scripts
├── configs/
├── tests/
└── scripts/
```

## Tech stack

- **Framework:** FastAPI
- **Model serving:** Ollama
- **Orchestration:** custom router in `app/core/orchestrator.py`, dispatches each request to the appropriate domain agent

## Running locally

```bash
cp .env.example .env
pip install -r requirements.txt

# Pull and serve the model via Ollama
ollama pull qwen3.8-27b
ollama serve

# Run the service
uvicorn app.main:app --reload --port 8001
```

## Roadmap

- [ ] Ship first agent domain
- [ ] Add additional domains as the project scales
- [ ] Shared RAG layer across domains
- [ ] Integrate with the upstream API gateway (REST, JWT middleware)