# CLAUDE.md — Catronaut (ai-service)

> Persistent project context. Read this first at the start of any session on this repo.

## STATUS (update this block whenever work lands)

- **Last synced with code:** 2026-08-31
- **Branch:** `feat/tool-registry` (off `develop`, not yet pushed/PR'd)
- **Done: ROADMAP Phase 0 AND Phase 1 in full** (M0.1–M0.5, M1.1–M1.5), all merged to `develop`
  via PR #4 and PR #6. M1.2 = no retry, by decision; M1.5's JSONL persistence deferred to M6.2, by
  decision — both documented in §6, not loose ends. The service boots and answers with a real
  `qwen3:4b`, with per-run token/latency metrics in the logs.
- **Phase 2 started: M2.1 done (tool definition + registry), on this branch, not yet merged.**
  Shipped `app/core/tools/base.py` (`Tool` ABC) and `app/core/tools/registry.py`
  (`ToolRegistry`) — see ROADMAP.md M2.1 for the frozen shapes. No concrete tools yet (M2.4), not
  wired into `Agent`/`Orchestrator` yet (that needs M2.2/M2.3 first). 22 tests pass (17 + 5 new).
- **Next up:** M2.2 (tool-call parsing, validation, repair) — the hard gate. Its tool-call
  envelope must be frozen before M4.2 (the loop) can be finalized — verify every schema decision
  against `qwen3:4b` (prompt-style tool calling per its `ModelProfile`) before assuming the 27B's
  native tool calling.
- **Do not redo Phase 0 or Phase 1.** The missing `config.py`, missing `model_provider/`, UTF-16
  `requirements.txt`, empty `Dockerfile` and `.env` drift are all **fixed**. `ModelProfile`,
  `RunContext`, usage metrics all exist — don't re-derive them.
- **Git flow note:** PR #2 merged straight to `main` and had to be reverted (PR #3) — `main` only
  takes promotions from `develop`, never a direct feature-branch target. See §7.

---

## 1. Purpose and deployment context

**Catronaut** is a self-hosted, local-first AI service exposing **domain-based agents** over HTTP.
It is not a chatbot wrapper — the design goal is that *each agent domain is a self-contained
vertical* (its own agent class, prompts, tools, skills, eval dataset, and eventually its own
LoRA adapter), sitting on top of a shared core (model provider, orchestrator, memory/RAG, config).

- **First / current domain: `ui_ux`** — analyzes a UI (text description or screenshot) and returns
  actionable feedback on layout, accessibility, and design consistency. Currently **single-shot**:
  one system prompt + one user message + one model call. No tools, no loop, no retrieval yet.
- **Second domain scaffolded (dirs only, no code): `code_review`**.

### This service runs behind an existing Go API gateway

This is a load-bearing architectural fact, not a footnote:

- **The gateway owns public routing, API versioning, and JWT auth.** This service does **not**
  version its own paths and has **no** `/api`, `/v1`, or `/ai` prefix. Routes are domain-relative:
  `POST /ui-ux/analyze`. The gateway maps its public path onto that.
- **Do not add auth middleware, rate limiting, or CORS here** unless explicitly asked — the gateway
  already does it. Duplicating it causes double-enforcement bugs.
- **Assume the service is not publicly reachable.** It trusts its caller.
- `/health` stays unprefixed for gateway and container probes.
- If per-user context is ever needed, it should arrive as an upstream-injected header from the
  gateway (e.g. `X-User-Id`), never as a JWT this service parses itself.

## 2. High-level architecture

```
Go API gateway  (public routing, versioning, JWT)
  -> POST /<domain>/...
    -> app/api/<domain>.py        (FastAPI router, thin — no business logic)
      -> app.state.orchestrator   (domain registry, built once at startup)
        -> app/domains/<domain>/agent.py   (Agent subclass, owns prompt assembly)
          -> app/core/model_provider       (ModelProvider interface -> OllamaProvider)
            -> Ollama HTTP API
```

Invariants the code honors — **keep these**:

1. **One model provider instance, shared.** Built once in `app/core/lifespan.py`, injected into
   every agent via `Orchestrator`, closed on shutdown. *Never* construct a provider inside an
   agent or a route handler.
2. **Routers are thin.** A route resolves the agent and awaits `handle()`. Nothing else.
3. **Agents never touch provider-shaped dicts.** They call `provider.extract_content(raw)`.
   Response-shape knowledge lives in the provider, not the domain.
4. **Core is closed to domain changes.** A new domain = new folder + one line in
   `app/domains/registry.py` + one router. `app/core/` is not edited.
5. **No public-API concerns in this service.** See §1 — the gateway owns them.

## 3. Model setup — prod vs dev

| | Production | Dev (current, installed) |
|---|---|---|
| Model | **`qwen3.8-27b`** (decided) | `qwen3:4b` (also `qwen3:8b` pulled) |
| Serving | Ollama on a GPU server | Ollama 0.33.1 |
| Vision | Yes | **No** — `qwen3:4b` / `qwen3:8b` are text-only |
| Speed | GPU | **CPU-only here, ~8 tok/s measured** |
| Tool calling | Reliable | Weak — expect malformed JSON, hallucinated names, skipped calls |

**On the prod tag:** `qwen3.8-27b` is the decided target. Verified 2026-08-29: it returns **404
from the public Ollama library** (`registry.ollama.ai/v2/library/qwen3.8-27b`), so it cannot be
`ollama pull`-ed as-is — it will need a Modelfile or a private registry on the GPU server. Set it
via `MODEL_NAME`; nothing hardcodes it.

### Measured behaviour of `qwen3:4b` (tested, not assumed)

Verified directly against the running Ollama. This drives real code — do not re-litigate it from
memory:

- **The 4B always reasons. `think: false` does NOT disable reasoning** — it only stops Ollama from
  splitting reasoning into a separate `message.thinking` field. The reasoning then lands inside
  `message.content`, terminated by a bare `</think>` with **no opening tag**.
- Same prompt, measured:
  - `think: false` → **44s**, 646 tokens, `done_reason: stop`, complete answer after the tag.
  - `think: true` → **105s**, 900 tokens of pure reasoning, cut off before answering.
  - Qwen3's `/no_think` soft switch → did **not** suppress reasoning either.
- **Therefore `MODEL_THINK=false` is the correct setting, not a hack.** It measurably shortens
  reasoning. `OllamaProvider.extract_content` strips the leaked block with `_LEAKED_THINK`.
  There are regression tests for this in `tests/test_api.py`.
- Reasoning tokens are output tokens: they cost both latency and context budget.
- `/api/embed` returns *"This server does not support embeddings"* for this runner — RAG will
  need a dedicated embedding model (ROADMAP M5.3).

### Design implications

- **Do not design for the 27B and hope the 4B keeps up.** Verify every prompt, tool schema, and
  loop against `qwen3:4b` first. If it only works on 27B, it is not done.
- **Keep system prompts short and imperative.** One job per prompt, not one mega-prompt.
- **Never trust raw tool-call JSON from the 4B.** Validate/repair (Pydantic parse → one bounded
  re-ask). A validator must sit between model output and execution.
- **Budget for reasoning.** Any token budget must assume the 4B burns several hundred tokens
  reasoning before answering. Do not cap `num_predict` tightly — it truncates mid-reasoning and
  yields an empty answer (observed).
- **Timeouts must be generous.** `MODEL_TIMEOUT_S=600`. A 300s timeout already failed in practice
  on a two-part UI/UX prompt.
- **Vision stays optional and unblocking.** `UIUXAgent` sends `images`; the text-only dev model
  ignores them. Revisit only once the real 27B runs on prod (decided).

## 4. Current structure under `app/`

```
app/
├── __init__.py
├── main.py                     FastAPI app, logging setup, /health, exception handlers
├── api/
│   ├── router.py               api_router, no prefix — the gateway owns versioning
│   └── ui_ux.py                POST /ui-ux/analyze
├── core/
│   ├── config.py               pydantic-settings `Settings` + `settings` singleton
│   ├── model_profile.py        ModelProfile (context/vision/tools/tier) + get_model_profile()
│   ├── run_context.py          RunContext(run_id, domain, model_profile, session_id, ...)
│   ├── exceptions.py           CatronautError tree + register_exception_handlers()
│   ├── lifespan.py             startup: OllamaProvider + Orchestrator; shutdown: aclose()
│   ├── agent_base.py           abstract `Agent`; `_new_run_context()`; `_build_output()` also
│   │                           extracts usage + logs the structured "done" line (M1.5)
│   ├── orchestrator.py         domain -> agent instance; raises UnknownDomainError
│   ├── model_provider/
│   │   ├── base.py             ModelProvider ABC: chat(), aclose(), extract_content(),
│   │   │                       extract_usage() -> RunUsage, embed()
│   │   └── ollama_provider.py  httpx.AsyncClient; error mapping; </think> stripping;
│   │                           extract_usage() from prompt_eval_count/eval_count/total_duration;
│   │                           health()
│   └── tools/                  (M2.1) definition + registry only — no concrete tools yet
│       ├── base.py             Tool ABC: name, description, args_schema, async run(args)
│       └── registry.py         ToolRegistry: get(name), schema() -> [{name,description,
│                                parameters}], rejects duplicate names
├── domains/
│   ├── registry.py             AGENT_REGISTRY — the one place a domain is declared
│   └── ui_ux/
│       ├── agent.py            creates a RunContext, builds [system, user(+images)], chat()
│       └── prompts.py          SYSTEM_PROMPT constant
└── schemas/
    └── agent.py                AgentInput{prompt, image_base64?},
                                 AgentOutput{run_id, result, model, raw?}
```

Top-level (dirs tracked via `.gitkeep`, contents gitignored):
`models/base`, `models/adapters/{ui_ux,code_review}`, `data/{raw,processed,vectorstore}`,
`evaluation/{datasets/{ui_ux,code_review},results,scripts}`, `configs/`,
`scripts/smoke_test.py`, `tests/test_api.py` (17 tests) + `tests/test_tools.py` (5 tests),
`docs/FLOW.md` (see §5 for its English-only exception).

## 5. Conventions — follow these

- **Python 3.10** (that is the venv version — `str | None` is fine, newer syntax is not).
  **Every package has an `__init__.py`.** Keep it that way.
- **Naming**: domains are `snake_case` on disk and as registry keys (`ui_ux`), `kebab-case` in
  URLs (`/ui-ux`). Agent classes are `<Domain>Agent`. Settings that configure the model are
  prefixed `model_` (`model_num_ctx`, `model_timeout_s`, `model_think`).
- **No path versioning in this service.** See §1.
- **Async everywhere** on the request path. The provider uses `httpx.AsyncClient` — never
  `requests`, it would block the event loop.
- **DI via `app.state`**, read off `Request` in the route. `Depends()` is not used yet.
- **Config**: one `settings` object from `app.core.config`. Never read `os.environ` directly.
  `Settings` sets `protected_namespaces=()` because pydantic v2 reserves the `model_` prefix.
- **Model-specific behaviour goes through `settings.model_profile`, never `if model_name == ...`.**
  Add a new model by adding an entry to `_PROFILES` in `app/core/model_profile.py`; an unregistered
  tag falls back to a conservative profile with a logged warning rather than guessing.
- **Every agent creates a `RunContext` first thing in `handle()`** via `self._new_run_context()`,
  and threads it into `self._build_output(run, raw, content)`. Log lines inside `handle()` should
  include `run_id=%s` so a request is traceable end to end; `AgentOutput.run_id` gives the caller
  the same ID for cross-referencing.
- **Token/latency metrics go through `ModelProvider.extract_usage(raw) -> RunUsage`, never read
  off `raw` directly in `agent_base.py` or a domain agent.** Same reasoning as `extract_content`:
  the field names (`prompt_eval_count`, `eval_count`, `total_duration` for Ollama) are
  backend-specific. `_build_output` already calls it and sets `run.usage` — don't duplicate that
  in a domain agent.
- **Errors**: raise a `CatronautError` subclass; the handler maps it to
  `{"error": {"code", "message"}}`. Never let a bare exception reach the client.
  `ProviderError` → 502, `UnknownDomainError` → 404, `DomainError` → 422.
- **Prompts**: module-level constants in each domain's `prompts.py`. No templating engine.
- **`raw` in responses is dev-only**, gated by `settings.expose_raw_response`.
- **Tests stub the model.** Real generation takes minutes; live checks go in
  `scripts/smoke_test.py`, not in pytest.
- **Project docs (`CLAUDE.md`, `README.md`, `ROADMAP.md`) are English-only.** No bilingual
  sections. `docs/FLOW.md` is a deliberate exception — a Vietnamese, newbie-facing code
  walkthrough, not a project-infrastructure doc — and stays Vietnamese. Don't translate it or
  use it as precedent for the others. (Chat explanations stay in Vietnamese regardless — that's
  a separate, standing preference.)

## 6. Still open / not yet done

**Resolved decisions — do not re-ask:**

- Prod model tag: **`qwen3.8-27b`**. Needs a Modelfile / private registry (see §3).
- Postgres: **coming later**, on the GPU server; a Neon URL is the likely first form.
  Stays commented in `.env.example` until ROADMAP M3.4.
- Vision: **stays optional**. Revisit only after the real 27B runs on prod.
- Retry: **not implemented here, on purpose** — the Go gateway owns it (see limitation #1 below).
- Run-log JSONL persistence: **deferred to ROADMAP M6.2**, not built speculatively now — see the
  M1.5 section in `ROADMAP.md` for why.

**Known limitations of the current implementation:**

1. **No retry, by decision (2026-08-30).** A transport failure surfaces immediately as 502.
   The Go gateway already retries; adding a second retry layer here would stack with it and risk
   multi-minute worst-case latency on top of the 44s–600s a single call already takes. Do not
   re-add this without a reason that outweighs that.
2. **No tool execution, no loop, no RAG, no context budgeting, no session/history.** `UIUXAgent`
   is still single-shot and stateless. `Tool`/`ToolRegistry` exist (M2.1) but nothing calls them
   yet — no parsing of model tool-call output (M2.2), no execution policy (M2.3), no concrete
   tools (M2.4), not wired into `Agent`/`Orchestrator`. This is the remaining ROADMAP.
3. **`ModelProvider.embed` raises `NotImplementedError`** by design (ROADMAP M5.3), and the dev
   Ollama runner has embeddings disabled anyway.
4. **No CI, no linter/formatter config.** `configs/` is still empty.
5. **Local pip is broken by an unrelated env var**: `PostgreSQL\15\ssl\certs\ca-bundle.crt` is set
   as the CA bundle and does not exist. Workaround used when installing:
   `REQUESTS_CA_BUNDLE=$(python -c "import certifi;print(certifi.where())")`.

## 7. Working agreement

- **Git flow: `feat/<topic>` branches off `develop`, PRs target `develop`. Never target or push
  to `main` directly.** `main` is a separate, more stable line — promoted from `develop`
  deliberately, not a default PR target. (PR #2 was merged straight to `main` and had to be
  reverted for exactly this reason — see `git log main` around 2026-08-30 if the history needs
  explaining.) Before starting any new branch: `git checkout develop && git pull`, then branch
  from there.
- Conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).
- Surgical diffs. Don't refactor adjacent code unasked. Pause and confirm before touching more
  than 3 files.
- Ask before implementing.

### Documentation workflow — mandatory, every time work lands

This is not optional bookkeeping; it is how parallel sessions avoid redoing finished work.

1. **Update `ROADMAP.md` in the same change as the code.** Mark the milestone `[x]` (or
   `PARTIALLY DONE` with the remaining bullets still `[ ]`), and write what actually shipped —
   file names, frozen signatures, and any measured numbers that drove the design.
2. **Update the STATUS block at the top of this file.** It must always answer three questions:
   what is done, what is next, and what must not be redone.
3. **Record measurements, not impressions.** If a decision came from a test against the real
   model, put the numbers in `ROADMAP.md` so nobody re-derives them.
4. **Move resolved questions out of §6 "open" and into "Resolved decisions".** Never leave a
   settled question phrased as open.
5. **English only in `.md` files.**
