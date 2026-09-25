# Catronaut — ai-service

`ai-service` is the agent harness behind **Catronaut**, a multi-domain agent platform. The first
domain, `ui_ux`, turns a request such as "build an e-commerce site" into a frontend-only
**Next.js** project that runs live in the user's browser. The agent asks clarifying questions
when information is missing, proposes an art direction, plans, writes the code, and verifies it.
Award-level visual craft is the goal. A cybersecurity domain comes later on the same core.

> **Status:** planning. There is no code yet — Phase 0 of the [roadmap](ROADMAP.md) starts here.

## How it fits together

```
Browser (frontend team) ──► API gateway ──► ai-service (this repo) ──► vLLM · Qwen3.8-27B
                                                 │                 └──► MCP servers (context7, …)
                                                 └──► project-service (file tree, versions)
```

- **Model:** Qwen3.8-27B served by vLLM — see [docs/qwen3.8-27b-reference.md](docs/qwen3.8-27b-reference.md).
- **Preview:** generated projects run in the user's browser on the Sandpack classic bundler with
  Next.js shims. `ai-service` never builds or runs generated code; it only parses it.
- **Files:** the project file tree lives in `project-service`; `ai-service` works on a copy during
  a run and writes back.
- **Out of scope here:** the frontend, the API gateway and `project-service` (owned by other teams).

## Planned stack

Python + FastAPI · pydantic · `openai` SDK against vLLM · `mcp` SDK · SSE streaming ·
tree-sitter for static checks · Playwright for evaluation · `uv`, `ruff`, `pyright`, `pytest`.
Decisions and their reasons are recorded in [ROADMAP.md](ROADMAP.md) §2.

## Documentation

| Document | What it is |
|---|---|
| [ROADMAP.md](ROADMAP.md) | Decisions, assumptions, architecture, and the phased plan (M0.1–M8.2) |
| [docs/book-guide/](docs/book-guide/README.md) | Per-chapter steps from *Hiểu sâu về AI Agent*, with section references |
| [docs/ai-agent-book/](docs/ai-agent-book/README.md) | The book itself (Vietnamese Markdown), the reference for harness design |
| [docs/qwen3.8-27b-reference.md](docs/qwen3.8-27b-reference.md) | Model card notes for Qwen3.8-27B |
| [docs/vn/](docs/vn/README.md) | Vietnamese translations for human readers |

## Conventions

- English documents are canonical. `docs/vn/` holds Vietnamese copies for people; agents do not
  read it, and when the two differ the English version wins.
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, …) on a dedicated
  branch — see [.claude/skills/github-git-workflow/SKILL.md](.claude/skills/github-git-workflow/SKILL.md).
