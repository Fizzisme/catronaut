# CLAUDE.md — Catronaut (ai-service)

> Persistent project context. Read this first at the start of any session on this repo.

## STATUS (update this block whenever work lands)

- **Last synced with code:** 2026-08-31
- **Branch:** `docs/site-gen-phase9` (off `develop`). M2.1–M2.4 and the phase restructure are all
  merged to `develop` (PRs #7–#11).
- **⚠ ROADMAP phases were restructured on 2026-08-31 — milestone numbers moved.** Phase 1 was
  renamed **Runtime** (it is scaffolding, not the agent harness), a new **Phase 3 — Skills** was
  inserted, and the old Phases 3–6 became **4–7**, plus a new **Phase 8 — Extensibility and
  safety**. So `M3.x` now means *skills*, not context; the context budgeter is `M4.1`, the ReAct
  loop is `M5.2`, RAG embeddings are `M6.3`, fine-tuning data collection is `M7.2`.
  **M0.x / M1.x / M2.x kept their numbers**, so every commit message in `git log` is still
  accurate. If a stale number surfaces anywhere, it is a doc bug — fix it, don't re-derive.
- **Done: ROADMAP Phase 0 AND Phase 1 in full** (M0.1–M0.5, M1.1–M1.5), all merged to `develop`
  via PR #4 and PR #6. M1.2 = no retry, by decision; M1.5's JSONL persistence deferred to M7.2, by
  decision — both documented in §6, not loose ends. The service boots and answers with a real
  `qwen3:4b`, with per-run token/latency metrics in the logs.
- **Phase 2 (Tools) is fully done, M2.1 through M2.4 — the whole tool layer through a real tool
  pack.** `Tool`/`ToolRegistry` (M2.1), `parsing.py`/`resolver.py` (M2.2, envelope frozen),
  `policy.py`/`executor.py` (M2.3), and now `app/domains/ui_ux/tools/` — 4 concrete tools:
  `check_contrast`, `lookup_heuristic`, `format_review`, `fetch_docs` (M2.4, merged). 78 tests
  pass. **Nothing calls any of this yet** — wiring the tool layer into an agent is the loop's job
  (M5.1/M5.2).
- **⚠ `qwen3:4b` DOES support native tool calling — measured 2026-08-31, and the profile was
  wrong.** Ollama reports `capabilities: ['completion','tools','thinking']`; a real call returned
  a well-formed `message.tool_calls` (37.3s, 510 tokens). `ModelProfile` now says
  `supports_native_tools=True`, `tool_call_style="native"` for that tag. The old `False`/`"prompt"`
  was a guess from M1.1, made while nothing consumed the field. **Do not restore it.** The prompt
  envelope path is implemented and tested too — it is the fallback for models without the `tools`
  capability, not the 4B's only option.
- **`fetch_docs` is the pack's one network tool** — added beyond the ROADMAP's original suggested
  set, at the user's request. It makes an outbound HTTP GET, which is exactly ROADMAP M8.3's
  trigger #3. Mitigated with a tool-local SSRF guard (DNS-resolved address allowlist, no
  redirects followed) rather than building the full M8.2 permission layer early — see M2.4's and
  M8.2's ROADMAP writeups for why that's the right call for now, not a shortcut taken silently.
- **Live-verified with all 4 tools registered together: 4/4 correct tool selection** (measured
  2026-08-31, `scripts/ui_ux_tool_pack_check.py`). Closes the gap M2.2 left open — selection
  accuracy had only been checked with one tool. Still one data point; re-verify before adding
  tools past the ~3–5 [4B gap] cap.
- **A "view this UI via vision" tool was requested and explicitly NOT built** — three concrete
  blockers recorded in ROADMAP "Still open": `qwen3:4b` has no vision, `ToolExecutionResult` is
  typed `str` with no multimodal path back into the message list, and screenshotting needs a
  headless browser this service doesn't otherwise depend on. Don't build it speculatively; see
  the ROADMAP entry for what would need to exist first.
- **New: ROADMAP Phase 9 — `site_gen` — designed 2026-08-31, ZERO code written.** A new domain
  where a user says "build me an e-commerce site" and gets **real generated files back, previewed
  in the browser** — plus follow-ups like "that button's colour is wrong", which the agent fixes by
  reading and rewriting the file. Documentation only: milestones `M9.1`–`M9.8` in `ROADMAP.md`,
  nothing under `app/`. Decisions that must not be re-litigated:
  - **Separate domain, not a mode inside `ui_ux`** — `ToolPolicy` has no per-mode scoping, `ui_ux`
    is already at the measured tool cap, and mixing write-capable tools in would falsify the
    `ui_ux` sandbox claim in §6.
  - **This service never builds or runs generated code.** Preview is **Sandpack** (MIT) in the
    user's browser — zero server cost. StackBlitz WebContainer was rejected: commercial licence
    required, and its mandatory COEP/COOP headers risk breaking the Next.js frontend.
    **Consequence: M8.3 sandboxing is off the path entirely** — trigger #1 never fires.
  - **Sandpack has no `nuxt` template → unsupported frameworks fall back to `vite-react`**, and
    the response must say so.
  - **Stateless.** Workspace lives on disk keyed by `project_id`; conversation `history` is
    re-sent by the client each turn. **M4.4 session store is not needed** for either the discovery
    loop or iterative editing.
  - **Ambition is profile-split, not gated all-or-nothing** — `qwen3.8-27b` isn't running
    anywhere, so a large-only gate would make the phase permanently undone by this project's own
    rule. Mechanics are measurable on `qwen3:4b` now; only the full multi-page ambition is
    large-tier (M9.7, BLOCKED on GPU-server infra).
  - **Skills matter here and are on the path** (M3.1 → M9.6): skill content starts from
    OpenDesign's `SKILL.md` design-pattern files — verified **Apache-2.0, no NOTICE file**, so
    reuse is permitted with attribution. **RAG waits** until M6.1 decides what would even be
    indexed.
- **⚠ Build order was reprioritised 2026-08-31: `site_gen` (Phase 9) is the PRIMARY product.**
  The ROADMAP was written when `ui_ux` review was the product, so its phase order put RAG (5
  milestones) and fine-tuning (6) — both of which only make *review* better — ahead of code
  generation. Neither is needed to generate a project from a prompt. **Critical path is now
  `M4.1 → M4.2 → M5.1 → M5.2 → M9.1 → M9.2 → M9.3 → M9.4 → M9.5`** (through iterative editing —
  the product is not usable without it). Then `M3.1 → M9.6` adds skills and the ask-back turn.
  Fine-tuning and hooks are **deferred, not cancelled**; **RAG waits on M6.1** answering what
  would be indexed; **M8.3 sandboxing is off the path entirely** now that nothing is built
  server-side. **Read ROADMAP's "Suggested execution order" block, not the phase numbers** — the
  numbers are conceptual layering and deliberately do not match build order.
- **Next up:** **M4.1 (token budgeter)** — first item on the critical path; M5.1/M5.2 both need it.
  **M9.1 (workspace primitive) and M9.2 (file tools) can be built in parallel at any time** — pure
  Python, no model, no loop, exactly like M2.1 and M2.4 needed nothing running.
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
Of those, **skills do not exist yet** — the loading mechanism is ROADMAP M3.1, not shipped. The
rest of that list is either built or has a milestone.

- **First / current domain: `ui_ux`** — analyzes a UI (text description or screenshot) and returns
  actionable feedback on layout, accessibility, and design consistency. Currently **single-shot**:
  one system prompt + one user message + one model call. It has a 4-tool pack (M2.4) that
  **nothing calls yet** — no loop, no retrieval.
- **Second domain scaffolded (dirs only, no code): `code_review`**.
- **Third domain planned, not yet scaffolded: `site_gen` — and it is the primary product.**
  Generates a small project's worth of real files from a prompt ("build me an e-commerce site"),
  then edits them on follow-up ("that button's colour is wrong"). Two output modes: plain
  HTML/CSS/JS when no framework is named, otherwise files shaped for a **Sandpack** template
  (falling back to `vite-react` for anything Sandpack cannot render, `nuxt` included).
  **This service only writes files — the frontend renders the preview via Sandpack; nothing is
  built or executed here.** Designed as ROADMAP Phase 9 (M9.1–M9.8); nothing under
  `app/domains/site_gen/` exists yet.

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
| Tool calling | Reliable, native (unverified — tag not running) | **Native works** (measured 2026-08-31); 4/4 correct selection with 4 tools registered |

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
  need a dedicated embedding model (ROADMAP M6.3).
- **Tool calling works on the 4B, both ways** (measured 2026-08-31, ROADMAP M2.2):
  - Ollama reports `capabilities: ['completion', 'tools', 'thinking']` for `qwen3:4b`.
  - Native (`tools` param) → correct `message.tool_calls`, 37.3s, 510 response tokens. **The
    call goes into the structured field and `content` after `</think>` is empty**, which
    `extract_content` raises on — so never resolve a tool call through it.
  - Prompt envelope → clean `{"tool": ..., "args": {...}}`, unfenced, 29.1s, 633 tokens.
  - Given a question needing no tool, it answered in prose and **did not invent a call**.
  - Caveat: one tool in the registry. Selection accuracy with 3–5 tools is still unmeasured.

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
│   │   │                       extract_tool_calls() -> [{name,arguments}],
│   │   │                       extract_usage() -> RunUsage, embed()
│   │   └── ollama_provider.py  httpx.AsyncClient; error mapping; </think> stripping;
│   │                           extract_usage() from prompt_eval_count/eval_count/total_duration;
│   │                           wraps registry schema into Ollama's function envelope; health()
│   └── tools/                  (M2.1-M2.3) the shared tool machinery — definitions, registry,
│       │                        parsing, execution policy. Concrete tools live per-domain (see
│       │                        domains/ui_ux/tools/). Nothing here is wired into an agent yet.
│       ├── base.py             Tool ABC: name, description, args_schema, read_only (no
│       │                        default), timeout_s (default 30.0), async run(args)
│       ├── registry.py         ToolRegistry: get(name), schema() -> [{name,description,
│       │                        parameters}], rejects duplicate names
│       ├── parsing.py          (M2.2) pure: ToolCall/NoToolCall/ToolCallFailure,
│       │                        parse_envelope(), validate_call(), build_tool_instructions()
│       ├── resolver.py         (M2.2) ToolCallResolver — native vs prompt path by
│       │                        ModelProfile.tool_call_style; exactly ONE repair turn
│       ├── policy.py           (M2.3) ToolPolicy — per-domain name allowlist only;
│       │                        capability declaration is M8.2, not this
│       └── executor.py         (M2.3) ToolExecutor.execute(run, call) -> ToolExecutionResult;
│                                allowlist -> timeout -> catch -> truncate; never raises
├── domains/
│   ├── registry.py             AGENT_REGISTRY — the one place a domain is declared
│   └── ui_ux/
│       ├── agent.py            creates a RunContext, builds [system, user(+images)], chat()
│       ├── prompts.py          SYSTEM_PROMPT constant
│       └── tools/               (M2.4) TOOLS = 4 concrete Tool instances, not wired in yet
│           ├── accessibility.py check_contrast — real WCAG contrast ratio
│           ├── heuristics.py    lookup_heuristic — Nielsen's 10, static, enum topic
│           ├── report.py        format_review — 3 flat params -> Markdown report
│           └── web.py           fetch_docs — the pack's one network tool; SSRF guard
└── schemas/
    └── agent.py                AgentInput{prompt, image_base64?},
                                 AgentOutput{run_id, result, model, raw?}
```

Top-level (dirs tracked via `.gitkeep`, contents gitignored):
`models/base`, `models/adapters/{ui_ux,code_review}`, `data/{raw,processed,vectorstore}`,
`evaluation/{datasets/{ui_ux,code_review},results,scripts}`, `configs/`,
`scripts/smoke_test.py` + `scripts/tool_call_check.py` (live M2.2 check) +
`scripts/ui_ux_tool_pack_check.py` (live M2.4 check, all 4 tools + 1 real fetch; none in pytest),
`tests/test_api.py` (17) + `tests/test_tools.py` (5) + `tests/test_tool_parsing.py` (22) +
`tests/test_tool_execution.py` (8) + `tests/test_ui_ux_tools.py` (26), `docs/FLOW.md` (see §5
for its English-only exception).

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
- **Tool calls go through `ModelProvider.extract_tool_calls(raw)`, never `raw["message"]
  ["tool_calls"]`.** Same rule as `extract_content` / `extract_usage`. And **never resolve a tool
  call through `extract_content`** — on the native path the 4B leaves `content` empty and
  `extract_content` raises by design; ask for structured calls first (`ToolCallResolver` does).
- **Tool-call style is read from `ModelProfile.tool_call_style`**, never branched on a model name.
  The prompt envelope `{"tool": ..., "args": {...}}` is frozen (ROADMAP M2.2) — M7.3 plans to
  fine-tune on it, so changing it is an API break, not a refactor.
- **A validated `ToolCall` runs through `ToolExecutor.execute(run, call)`, never `tool.run(args)`
  directly.** The executor is what applies the allowlist, the per-tool timeout, and result
  truncation (ROADMAP M2.3) — calling `run()` directly skips all three.
- **Every new `Tool` subclass must set `read_only`** (no default, on purpose — see
  `app/core/tools/base.py`). Forgetting it is a subtle bug, not a loud one: the class still
  imports fine, it just fails at `ToolExecutor.execute()` when it reads `tool.read_only`.
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
  Stays commented in `.env.example` until ROADMAP M4.4.
- Vision: **stays optional**. Revisit only after the real 27B runs on prod.
- Retry: **not implemented here, on purpose** — the Go gateway owns it (see limitation #1 below).
- Run-log JSONL persistence: **deferred to ROADMAP M7.2**, not built speculatively now — see the
  M1.5 section in `ROADMAP.md` for why.
- Phase structure (2026-08-31): audited against a 9-component agent-harness taxonomy. Phase 1
  renamed **Runtime**, **Phase 3 — Skills** inserted, old Phases 3–6 renumbered to 4–7, new
  **Phase 8 — Extensibility and safety** (hooks → permissions → sandbox-if-triggered →
  sub-agents). Don't re-audit; see the STATUS block for the number mapping.
- Sandboxing: **not needed for 3 of the `ui_ux` pack's 4 tools** — `check_contrast`,
  `lookup_heuristic`, and `format_review` are pure computation / in-process lookup / string
  formatting. **`fetch_docs` is the exception: it makes an outbound request to a model-supplied
  URL**, which is ROADMAP M8.3's trigger #3. It ships with a tool-local SSRF guard
  (DNS-resolved address allowlist, no redirects, size caps) instead of the full M8.2 permission
  layer — a deliberate, documented trade, not an oversight. See ROADMAP M8.2's revised assessment
  for why, and what changes when M8.2 lands. **Do not restate this bullet as "the `ui_ux` pack
  needs no sandbox"** — that was true before `fetch_docs` and is not true now.
- Sub-agents: **last milestone (M8.4)**, after the loop is stable. Isolated rebuilt context,
  subset permissions, structured-summary returns — never an inherited parent transcript.
- Preview for `site_gen`: **Sandpack in the user's browser** (MIT, no licence fee, no COEP/COOP
  headers). WebContainer rejected — commercial licence + headers that could break the Next.js
  frontend. **This service builds and runs nothing**, so ROADMAP M8.3 sandboxing is off the path.
- `site_gen` statefulness: **none.** Workspace on disk keyed by `project_id`, conversation
  `history` re-sent by the client each turn. M4.4 session store is not required.
- Unsupported frameworks in `site_gen`: **fall back to `vite-react`** and say so in the response.
  Sandpack has no `nuxt` template.
- Skill content: **starts from OpenDesign's `SKILL.md` files** (Apache-2.0, no NOTICE — reuse
  allowed with a licence copy, attribution, and a statement of changes). Select a handful, trim
  each to ≤300 tokens; do not import all 533.

**Known limitations of the current implementation:**

1. **No retry, by decision (2026-08-30).** A transport failure surfaces immediately as 502.
   The Go gateway already retries; adding a second retry layer here would stack with it and risk
   multi-minute worst-case latency on top of the 44s–600s a single call already takes. Do not
   re-add this without a reason that outweighs that.
2. **No loop, no RAG, no context budgeting, no session/history, and no agent uses the tool
   layer.** `UIUXAgent` is still single-shot and stateless. The entire tool layer is now done —
   `Tool`/`ToolRegistry` (M2.1), parsing/repair (M2.2), allowlist/timeout/truncation (M2.3), and
   4 real `ui_ux` tools (M2.4) — and tested, including live against `qwen3:4b`, but **nothing
   calls it**: not wired into `Agent`/`Orchestrator`. Wiring belongs to the loop (M5.1/M5.2);
   doing it earlier means building a mini-loop in `UIUXAgent` and deleting it later.
3. **No skills, no lifecycle hooks, no permission layer, no sub-agents.** Added to the ROADMAP on
   2026-08-31 after a taxonomy audit, none of them built: skills are Phase 3 (M3.1–M3.3), and
   hooks / permissions / sandbox-if-triggered / sub-agents are Phase 8 (M8.1–M8.4). Behavior that
   *would* be a hook is currently hardcoded — the "done" log line in `_build_output` (M1.5) is
   effectively a `run_end` hook, and M2.3's truncation/allowlist will be `post_tool_call` /
   `pre_tool_call`. M8.1 is a refactor onto a seam, not a rewrite; don't pre-build it.
4. **`ModelProvider.embed` raises `NotImplementedError`** by design (ROADMAP M6.3), and the dev
   Ollama runner has embeddings disabled anyway.
5. **No CI, no linter/formatter config.** `configs/` is still empty.
6. **Local pip is broken by an unrelated env var**: `PostgreSQL\15\ssl\certs\ca-bundle.crt` is set
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
