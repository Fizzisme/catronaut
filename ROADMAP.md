# Catronaut — Roadmap

> **Scope:** `ai-service`, the Catronaut agent harness. The frontend, the API gateway and
> `project-service` are owned by other teams and appear here only as contracts.
> **Version:** v1 · 2026-09-25. English is canonical; the Vietnamese copy in `docs/vn/` is for
> human readers only.

## 1. North star

Catronaut is a multi-domain agent platform. The first domain, `ui_ux`, turns a request such as
"build an e-commerce site" into a working **Next.js project (frontend only)**. The agent checks
whether it has enough information, asks structured questions when it does not, proposes an art
direction, plans, writes the code, and the project runs live in the user's browser. Award-level
visual craft ([awwwards.com](https://www.awwwards.com/) as the bar) is what sets it apart from
Claude Design-style tools. A second domain, `cyber` (cybersecurity), follows on the same core.

The model is **Qwen3.8-27B** served by **vLLM** ([model reference](docs/qwen3.8-27b-reference.md)).
The harness comes first; fine-tuning comes later, behind a gate.

## 2. Settled decisions

| # | Decision | Consequence |
|---|---|---|
| D1 | **Preview = Next.js subset + shims on the Sandpack classic bundler.** | The agent writes a real Next.js App Router project restricted to a frontend-only subset. The preview runtime (`next/*` shims, App Router emulation, Tailwind browser build) belongs to the frontend; `ai-service` defines and enforces the **preview contract**. Exported projects contain no shims. |
| D2 | **`ai-service` is Python + FastAPI.** | pydantic, the `openai` SDK against vLLM, the `mcp` SDK, `httpx`, SSE. TSX is verified parse-only with tree-sitter; a Node type-check sidecar is added only if evaluation shows parse-only lets too many errors through. Playwright (Python) for evaluation. |
| D3 | **Scope is `ai-service` only; the file tree lives in `project-service`.** | The workspace is an adapter over `project-service`. Versions and revert, locking and export are contract items with `project-service`. Development, tests and evaluation use a local workspace. |
| D4 | **English docs are canonical; `docs/vn/` holds Vietnamese copies for humans.** | Agents read the English docs only; `CLAUDE.md` (M0.1) states this. |
| D5 | **`ai-service` never builds or runs generated code.** Parsing is allowed. | The safety boundary is the cross-origin preview iframe in the user's browser. Browser-based checks run only in the offline evaluation pipeline. |

## 3. Facts that shape the plan

| # | Fact | Impact |
|---|---|---|
| F1 | Sandpack's `nextjs` template runs on Nodebox, which is pinned to Node 16, so Next.js ≥ 14 does not run ([sandpack#1104][sandpack-1104]). Nodebox templates (`nextjs`, `vite*`, `astro`, `node`) need a CodeSandbox licence for commercial use; classic templates (`react-ts`, `static`, …) are Apache-2.0 and self-hostable ([Sandpack FAQ][sandpack-faq]). | Led to D1. |
| F2 | Qwen3.8-27B is a hybrid model (Gated DeltaNet + Gated Attention). The vLLM v0.26 docs still list prefix caching as unavailable for hybrid models; the code has an experimental `mamba_cache_mode="align"` path ([vLLM v1 guide][vllm-hybrid]). | Without cache hits every agent step re-prefills the whole prefix. Measure in M0.2 before settling the context strategy. |
| F3 | vLLM serves the previous generation, Qwen3.6-27B, with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` ([vLLM Codex integration][vllm-codex]). | Starting configuration for Qwen3.8; verified in M0.2. |
| F4 | Qwen3.8's agentic scores were measured on the Claude Code harness. The model is natively vision-capable; thinking is on by default, with `reasoning_effort` and `preserve_thinking`. | Tool shapes follow Claude Code (Read, Write, Edit, Glob, Grep, TodoWrite). The same model can review screenshots. Reasoning must round-trip through the chat template. |
| F5 | open-design ships 19 skills and 71 design systems (`DESIGN.md`) for coding-agent CLIs, Qwen included ([open-design][open-design]); impeccable is the other design-skill reference. | Source material for skills and the design-system library. Licences are checked before porting (M4.2). |

## 4. Assumptions to confirm

- **A1.** Fresh start: no code from the previous Catronaut is reused; its documents are reference only.
- **A2.** The agent loop runs in `ai-service`. `project-service` is the source of truth for files; a
  run works on a working copy and writes back.
- **A3.** A GPU server runs vLLM with Qwen3.8-27B; a small model serves dev and CI smoke tests.
- **A4.** An API gateway in front handles authentication and injects the user id (the previous
  design used a Go gateway).
- **A5.** The frontend team owns the preview runtime. `ai-service` builds the M0.3 spike, writes the
  contract and hands it over; the evaluation pipeline reuses the same runtime.
- **A6.** No calendar dates. Each phase has exit criteria; estimates follow Phase 0.

## 5. Principles

1. Agent = LLM + context + tools; the harness is the product — [ch01] §1.1–1.2.
2. Constraints are enforced in code, not requested in prose — [ch05] §5.1.4.
3. "Done" is verified, not declared: a run succeeds only when its verifiers pass — [ch10] §10.4.3.
4. Context is KV-cache friendly: static prefix → history → dynamic tail — [ch02] §2.3.
5. Evaluate before optimising. Every harness layer sits behind a feature switch so it can be
   measured, and removed once the model no longer needs it — [ch07] §7.10, postscript.
6. Provider-neutral trajectories are logged from day one — [ch05] §5.1.5, [ch08] §8.14.
7. Tool shapes follow Claude Code to stay inside the model's training distribution (F4).
8. Security is architectural from the first line: context, execution and data-layer guardrails —
   [ch01] §1.2.5.

## 6. Architecture

```
Browser (frontend team): chat · question forms · file tree · preview (Sandpack classic + Next.js shims)
   │ run requests                ▲ SSE run events               │ preview errors + screenshots
   ▼                             │                              ▼
API gateway: authentication, user id, rate limits
   ├──► ai-service  ◄── scope of this roadmap (Python / FastAPI)
   │      core: LLM client · agent loop · context and compaction · tools · skills · MCP client
   │            · workspace adapter · verifiers · tracing
   │      domains: ui_ux (first) · cyber (later)
   │        ├──► project-service: file tree, versions, locks   [other team]
   │        ├──► vLLM: Qwen3.8-27B   [+ multi-LoRA later]
   │        └──► MCP servers: context7, …
   └──► project-service
```

## 7. Phases

Guides: every phase links to the per-chapter guides in [docs/book-guide/](docs/book-guide/README.md),
which summarise the steps of *Hiểu sâu về AI Agent* with section (§) references into the book.

### Phase 0 — Foundations and spikes

| ID | Milestone | Deliverable |
|---|---|---|
| M0.1 | Repository bootstrap | Own git repository; `uv`, `ruff`, `pyright`, `pytest`, CI; FastAPI skeleton; layout `app/core/`, `app/domains/ui_ux/`, `app/api/`, `evals/`, `docs/`; `CLAUDE.md` stating that English docs are canonical and agents do not read `docs/vn/`. |
| M0.2 | Model-serving spike | vLLM with the F3 flags; quantisation chosen for the GPU (BF16 ≈ 54 GB of weights, FP8 ≈ 27 GB); try MTP speculative decoding. Measure tool-call parse success (~50 scripted calls), TTFT and tokens/s at 8K/32K/64K context, **prefix-cache hit rate** (F2) and concurrent sessions; check that `enable_thinking`, `reasoning_effort` and `preserve_thinking` pass through vLLM → ADR-0001. |
| M0.3 | Preview spike | Sandpack classic bundler (self-hostable) with shims for `next/link`, `next/image`, `next/font`, `next/navigation` and metadata; App Router emulation from `app/**/page.tsx`, nested `layout.tsx` and `[slug]` segments; Tailwind through its browser build; dependency trials (motion, gsap, lenis, three/R3F); capture bundler and runtime errors; screenshot the iframe → ADR-0002, the **preview contract** (allowed vs forbidden: `"use server"`, `app/**/route.ts`, `next/headers`, `server-only`, Node APIs, …) and a vetted dependency list. |
| M0.4 | Service contracts | (a) Frontend ↔ `ai-service` through the gateway: run lifecycle (start, SSE stream, `needs_input`, resume, cancel) and a preview-report endpoint. (b) `ai-service` ↔ `project-service`: read the tree, batch writes, a version per run and revert, lease/lock, optimistic concurrency → ADR-0003. |
| M0.5 | Static-verification spike | tree-sitter (TSX) parsing, import resolution and preview-contract rules, run on the starter and on a corpus of seeded errors; measure what slips through and decide on a Node type-check sidecar → ADR-0004. |
| M0.6 | Book guides | [docs/book-guide/](docs/book-guide/README.md): per-chapter steps with book references, plus Vietnamese copies. **Done 2026-09-25.** |

**Exit:** tool calling works reliably against the real model; a Next.js starter renders in the
preview; ADR-0001 to ADR-0004 are accepted.
**Guides:** [ch01]; [ch02] §2.3; [ch04] §4.6; [ch06] §6.1–6.2.

### Phase 1 — Harness core (domain-agnostic)

| ID | Milestone | Deliverable |
|---|---|---|
| M1.1 | LLM client | `AsyncOpenAI` against vLLM with streaming; reasoning round-tripped per the chat template; retries only for retryable errors (429, 5xx, connection reset) with backoff and jitter; `finish_reason=length` detected, and a truncated tool call is **never executed**; provider-neutral message model. |
| M1.2 | Agent loop (ReAct) | Every tool call in a turn is handled; terminal states `done`, `needs_input`, `stopped_at_limit`, `failed`, `cancelled`; caps on iterations, wall clock and tokens; repeated-call fingerprints and consecutive-failure circuit breakers; every `tool_call` paired with a result before the next request; cancellation at safe points. |
| M1.3 | Tool framework | pydantic schemas with fail-fast validation; full descriptions (when to use, when not to, an example, return shape, cost); tool errors returned as structured observations with a recovery hint; explicit head + tail truncation that says how to read the rest. |
| M1.4 | Workspace adapter | `Workspace` interface. `ProjectServiceWorkspace` loads the tree at run start into a working copy, writes back to `project-service` and emits `file_changed`; `LocalWorkspace` serves dev, tests and evaluation. Path guard; per-run write quotas (size, count, extensions); project lease for the length of a run. |
| M1.5 | File tools | `Read` (line-numbered, `offset`/`limit`), `Write` (an existing file must have been read first), `Edit` (exact `old_string` → `new_string`: a unique match or a clear error), `Glob`, `Grep`, `TodoWrite`. Arguments are never silently transformed. |
| M1.6 | Context engineering | System prompt composed from named, byte-stable sections; KV-cache-friendly ordering; status bar computed in code (iteration n/max, counters, manifest summary); token budget; layered compaction with re-readable handles, built when measurements call for it. |
| M1.7 | Tracing | One JSON trace per run: model calls (tokens, duration, finish reason), tool calls (argument digest, status, elapsed time) and results. |
| M1.8 | Run API and streaming | FastAPI async runs with SSE (`thinking` and `message` deltas, `tool_call`, `tool_result`, `file_changed`, `needs_input`, `done`), resume and cancel. A full-site run takes minutes, so runs must be asynchronous. |
| M1.9 | Dev CLI and playground | `catronaut run "<prompt>"` on `LocalWorkspace`, plus a minimal dev page with a preview, to exercise the harness before the real frontend exists. |

**Exit:** on the real model the agent creates and edits files through tools, with complete traces;
CI smoke tests on the small model pass.
**Guides:** [ch01] §1.1.5; [ch02] §2.2–2.7; [ch04] §4.2, §4.5; [ch05] §5.1.4–5.1.8; [ch06] §6.2.

### Phase 2 — `ui_ux` MVP: from prompt to a Next.js project running in the preview

| ID | Milestone | Deliverable |
|---|---|---|
| M2.1 | Domain pack `ui_ux` | Prompt sections, tool allowlist, skills, knowledge, verifiers, evaluation set — the template every domain follows. |
| M2.2 | Starter and manifest | Deterministic scaffold from a starter vetted in the preview, written through the workspace adapter; `.catronaut/project.json` records the template, discovery answers, design decisions, and files with hashes. |
| M2.3 | Discovery | `ask_user` returns structured questions `{id, text, kind: single\|multi\|text, options}`; the run ends in `needs_input`; the frontend renders a form and all answers come back in one turn. The skill decides what to ask; the harness refuses to scaffold while required facts are missing. |
| M2.4 | Design brief and design system | `DESIGN.md` plus tokens (colour, type scale, spacing, radius, motion) in the workspace, chosen from a design-system library or derived from the user's input. |
| M2.5 | Plan | Sitemap and page/component list through `TodoWrite`; large requests confirm the plan with the user first. |
| M2.6 | Build and verify | After every write: tree-sitter parse, import resolution, preview-contract rules, dependency allowlist. A run is done only when the verifiers pass. |
| M2.7 | Preview feedback loop | During a run, a `check_preview` tool waits (with a timeout) for the frontend to report after re-rendering; otherwise errors arrive with the next turn. Self-fix rounds are capped. |
| M2.8 | Follow-up edits | "Change the button colour" becomes a targeted `Edit`; revert uses `project-service` versions; `reasoning_effort` per step is chosen by evaluation. |

**Exit:** the share of runs free of bundler and runtime errors on the evaluation set meets the
threshold set after the Phase 3 baseline.
**Guides:** [ch05]; [ch03] §3.1.2; [ch04] §4.6; [ch09] §9.2.2.

### Phase 3 — Evaluation harness (in parallel with Phase 2; a baseline is required before Phase 4)

| ID | Milestone | Deliverable |
|---|---|---|
| M3.1 | Task set v0 | 30–50 prompts: site type (landing, e-commerce, portfolio, SaaS, restaurant, …) × ambiguity; parameterised templates against contamination; trap tasks. |
| M3.2 | Deterministic verifiers | Workspace contract, parse checks, veto items (claims a file that does not exist, writes outside the workspace, …). |
| M3.3 | Browser checks | In CI and evaluation only: Playwright opens the preview (the same runtime as the frontend) → bundler and runtime errors, axe accessibility, basic performance, screenshots at three breakpoints. |
| M3.4 | Design score | Rubric and a vision judge on screenshots; a human-labelled sample for calibration; impeccable-style anti-pattern rules. |
| M3.5 | User simulator | For discovery: reveals preferences only when asked, with limited patience → questions asked vs outcome. |
| M3.6 | Reports | Pass@k and Pass^k; tokens, latency and cost per task; paired comparison between harness versions; failure attribution records. |

**Exit:** one command runs the evaluation and writes a report; the baseline is stored.
**Guides:** [ch07]; [ch09] §9.1.

### Phase 4 — Skills, knowledge and MCP

| ID | Milestone | Deliverable |
|---|---|---|
| M4.1 | Skill system | Agent Skills format (`SKILL.md` + frontmatter + `references/`); catalog in the static prefix; `load_skill` appends the body at the tail. |
| M4.2 | Design skills | Port impeccable and open-design (licences first; reviewed like code), rewritten for Qwen3.8; A/B tested through evaluation. |
| M4.3 | Knowledge base | File system before RAG: component patterns, the preview contract, accessibility, typography and colour, as Markdown with ~100-token abstracts and index pages. |
| M4.4 | MCP client | context7 and other servers; per-domain allowlist, timeouts, output truncation; MCP output tagged as untrusted data; web fetch behind an SSRF guard. |
| M4.5 | Assets | Images (a stock-photo API or placeholders), icons and fonts, so no site looks empty. |

**Exit:** evaluation shows the skills raise the design score over the baseline.
**Guides:** [ch02] §2.4.7, §2.5; [ch03] §3.2–3.3; [ch04] §4.3–4.4.

### Phase 5 — Awwwards-grade creative layer

| ID | Milestone | Deliverable |
|---|---|---|
| M5.1 | Technique taxonomy | Techniques seen on award-winning sites: editorial and asymmetric layout, oversized and kinetic type, scroll storytelling (GSAP ScrollTrigger, Lenis), page transitions, micro-interactions and custom cursors, WebGL/3D (three.js, R3F, shaders), texture (grain, noise, gradients), colour art direction. Learn **patterns**; never copy sites. |
| M5.2 | Recipe library | Each technique as a recipe proven in the preview, with guardrails: `prefers-reduced-motion`, mobile fallbacks, a performance budget, accessibility. |
| M5.3 | Creative direction | The agent proposes 2–3 directions (concept, type pairing, palette, motion language, layout idea); the user picks one; it is recorded in `DESIGN.md` and the manifest. |
| M5.4 | Visual self-review | The frontend sends preview screenshots; Qwen3.8 (vision) reviews them against the direction and the anti-pattern list and returns structured fixes, within a round cap. |
| M5.5 | Creative evaluation | A dedicated subset and a distinctiveness/craft rubric, judged pairwise (humans + judge) against the baseline. |

**Exit:** human raters prefer the creative-layer output over the baseline in at least X% of pairs
(X is set with the evaluation baseline).
**Guides:** [ch05] §5.2; [ch04] §4.5.1; [ch07] §7.5; [ch10] §10.2.

### Phase 6 — Production hardening (`ai-service` side)

| ID | Milestone | Deliverable |
|---|---|---|
| M6.1 | Scale and quotas | Stateless instances; run state in Redis or a database so any instance can resume or stream; per-user token and run quotas (GPU cost); user id from the gateway. |
| M6.2 | Persistence | Runs and traces in a database and object storage; files and versions stay in `project-service`. |
| M6.3 | Observability | Dashboards for latency, tokens, GPU, tool-error rate and run outcomes; alerts. |
| M6.4 | Security | Lethal-trifecta check per tool pack, egress control, MCP allowlist, secrets handling. |
| M6.5 | Export fidelity | CI runs a real `next build` on generated projects (no shims) so exports work; the export feature itself belongs to `project-service` and the frontend. |
| M6.6 | Sub-agents (gated) | Added only when evaluation shows that a second context with new information helps, e.g. a screenshot reviewer. |

**Guides:** [ch01] §1.2.5; [ch02] §2.7.6; [ch05] §5.1.9; [ch10].

### Phase 7 — Fine-tuning (gated)

**Gate:** the evaluation harness exists, enough traces are collected, and a failure class persists
after prompt, tool, constraint and context fixes have been tried.

| ID | Milestone | Deliverable |
|---|---|---|
| M7.1 | Data pipeline | Traces → verifier-filtered (rejection sampling) → SFT/DPO sets; train/eval split by task template; the Qwen3.8 licence checked for fine-tuning and adapter distribution. |
| M7.2 | SFT LoRA | Tool-use protocol, discovery behaviour, design skills; evaluated against the base model on boundary and retention sets. |
| M7.3 | Serving | vLLM multi-LoRA: one adapter per domain (`ui_ux`, `cyber`), routed by domain. |
| M7.4 | RL (later) | Verifiable rewards: no preview errors, accessibility, judge score. |

**Guides:** [ch08]; [ch09].

### Phase 8 — Second domain: cybersecurity (after Phases 2–3)

| ID | Milestone | Deliverable |
|---|---|---|
| M8.1 | Domain ADR | Execution sandbox for scanners, authorisation scope, egress rules, human approval — a different safety model from `ui_ux`. |
| M8.2 | Domain pack `cyber` | Reuses the core; its own prompts, tools, skills, verifiers and evaluation set. |

**Guides:** [ch01] §1.2.5; [ch04] §4.6; [ch05] §5.1.9.

## 8. Risks and open questions

| Risk or question | Mitigation |
|---|---|
| Prefix caching may not work for the hybrid model on vLLM (F2). | Measure in M0.2. If it is missing: tighter compaction, shorter prefixes, or evaluate SGLang. |
| The shims cannot reproduce every Next.js behaviour. | The preview contract limits the agent to a frontend-only subset; M6.5 checks real builds. |
| Licences: open-design, impeccable, Qwen3.8 (fine-tuning), the self-hosted Sandpack bundler. | Check before M4.2, M7.1 and M0.3 respectively. |
| Gateway timeouts vs long-lived SSE runs. | Settle in the M0.4 contract; resume from the manifest. |
| What `project-service` can offer (versions, lease, batch writes). | Agree in M0.4; `LocalWorkspace` unblocks development meanwhile. |
| The user edits files while a run is in progress. | Project lease and optimistic concurrency (M0.4, M1.4). |

## 9. Sources

- [Sandpack FAQ — licences for Nodebox templates][sandpack-faq]
- [codesandbox/sandpack#1104 — Nodebox pinned to Node 16][sandpack-1104]
- [vLLM — Codex integration (Qwen3.6-27B serving flags)][vllm-codex]
- [vLLM v0.26 V1 guide — hybrid models and prefix caching][vllm-hybrid]
- [open-design (many forks exist; confirm the upstream repository)][open-design]

[sandpack-faq]: https://sandpack.codesandbox.io/docs/resources/faq
[sandpack-1104]: https://github.com/codesandbox/sandpack/issues/1104
[vllm-codex]: https://docs.vllm.ai/en/stable/serving/integrations/codex
[vllm-hybrid]: https://github.com/vllm-project/vllm/blob/v0.26.0/docs/usage/v1_guide.md
[open-design]: https://github.com/ccfuncy/open-design
[ch01]: docs/book-guide/ch01-getting-started.md
[ch02]: docs/book-guide/ch02-context-engineering.md
[ch03]: docs/book-guide/ch03-memory-and-knowledge-base.md
[ch04]: docs/book-guide/ch04-tools.md
[ch05]: docs/book-guide/ch05-coding-agents-and-code-generation.md
[ch06]: docs/book-guide/ch06-interaction-observation-and-action-spaces.md
[ch07]: docs/book-guide/ch07-agent-evaluation.md
[ch08]: docs/book-guide/ch08-model-post-training.md
[ch09]: docs/book-guide/ch09-continuous-agent-evolution.md
[ch10]: docs/book-guide/ch10-multi-agent-collaboration.md
