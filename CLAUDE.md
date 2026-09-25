# Catronaut — ai-service

Agent harness for Catronaut (Python + FastAPI). See [ROADMAP.md](ROADMAP.md) for decisions and phases.

## Documentation language

- English documents are canonical. Read English docs only.
- Do **not** read `docs/vn/`: it holds Vietnamese copies for human readers, and the English version wins when they differ.

## Commands

- `uv sync` — install dependencies
- `uv run ruff check .` / `uv run ruff format .` — lint / format
- `uv run pyright` — type check (strict)
- `uv run pytest` — tests
- `uv run uvicorn app.main:app --reload` — dev server

## Layout

- `app/core/` — domain-agnostic harness (LLM client, agent loop, tools, workspace)
- `app/domains/ui_ux/` — first domain pack; `cyber` follows later
- `app/api/` — HTTP layer (runs, SSE)
- `evals/` — evaluation harness
- `docs/` — documentation

## Rules

- `ai-service` never builds or runs generated code; parsing only (ROADMAP D5).
- Conventional commits; work on a dedicated branch from `develop`.
