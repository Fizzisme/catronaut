# ADR-0003 — Service contracts: the run API and project files

- **Status:** Proposed 2026-09-27. Part (a) is ready for the frontend and gateway teams; part (b)
  waits for the `project-service` team to accept or amend the files module.
- **Milestone:** M0.4 (ROADMAP §7, Phase 0)
- **Hands over to:** the frontend and gateway teams ([run API contract](../run-api-contract.md));
  the `project-service` team ([project files requirements](../project-service-contract.md)).

## Context

`ai-service` sits between the frontend (through the API gateway) and `project-service` (D3).
Phase 1 builds the run API (M1.8) and the workspace adapter (M1.4) against these two contracts,
so they have to be settled first. The inputs:

- A full-site run takes minutes, and a single model call can stay silent for more than 13 s at
  60K context (ADR-0001). The gateway sits in the middle of a long-lived stream.
- The agent asks structured questions and waits for answers (M2.3).
- The preview renders in the user's browser and reports errors back (ADR-0002 Decision 3); errors
  from lazy chunks arrive seconds late.
- Book ch06: inputs are structured events consumed at safe points; cancellation happens at safe
  points; an interrupted tool is never reported as success (§6.2, §6.2.6).
- The owner wants the user to watch the agent work step by step, as in a coding-agent CLI:
  thinking with a token count, the tool being called and on what, its result, the plan.
- `project-service` exists, but its Phase 1 API is a **catalog** (project metadata, lifecycle,
  discovery). It has no files, no file history and no lock. It does have an optimistic
  concurrency pattern (`ETag` / `If-Match` / `412` on `row_version`) and an `ApiResponse<T>`
  envelope. Publishing is a user action in that catalog: a new Project is `DRAFT + PRIVATE`, and
  publishing makes it `PUBLISHED + PUBLIC`.
- Authentication: the gateway validates the user's access token, decodes it and forwards
  `X-User-Id` to the services behind it, which trust that header.

## Options considered

### How a run waits for the user's answers

| Option | For | Against |
|---|---|---|
| **The run ends in `needs_input`; the answers start a new run in the same session** | Nothing is held while the user thinks; no lease or stream left open; restart-safe | The next run rebuilds its context from the session history |
| The run pauses and resumes with the same id | One run per task | Holds state and the project lease for as long as the user is away |

### How files reach the preview during a run

| Option | For | Against |
|---|---|---|
| Write-through: every write goes to `project-service`, the event carries path and revision, the frontend refetches | Never out of sync | A round trip per write for the agent, another for the frontend; half-finished states stored |
| **The event carries the content; writes are flushed to `project-service` in batches at safe points** | The preview updates at once; few round trips; matches the M1.4 working copy | A crash between two safe points loses that step's writes (repaired by reloading the tree after the run) |

### Where project files live

| Option | For | Against |
|---|---|---|
| **A `files` module in `project-service`, requested from its team** | Keeps D3; one place for the frontend to read files; reuses the service's conventions | Depends on another team's schedule |
| `ai-service` stores the files | Not blocked | Breaks D3; `ai-service` becomes stateful storage; the frontend reads files from two services |
| A separate workspace service | Clear ownership | One more service to run, not justified yet |

### What the user and the agent may do at the same time

| Option | For | Against |
|---|---|---|
| Optimistic concurrency only | No lock to manage | The agent meets conflicts mid-run and has to recover from them |
| Lease only | Simple | A lease lost to expiry lets writes clobber each other silently |
| **Lease plus optimistic concurrency** | The lease prevents the common case; `If-Match` catches the rare one | Two mechanisms |

## Decision

1. **The run API** is the [run API contract](../run-api-contract.md): start (`POST /v1/runs`, with
   an idempotency key), an SSE stream, a run snapshot, cancel, and preview reports. At most one
   active run per project.
2. **`needs_input` ends the run.** The answers to a question form are the input of a new run in
   the same session.
3. **SSE with replay.** Every event has a per-run `seq` used as the SSE `id`; clients reconnect
   with `Last-Event-ID`; a heartbeat every 15 s; losing the stream never cancels the run; events
   are kept for 1 hour after the run ends. Gateway timeouts stop mattering.
4. **A step-by-step stream.** Steps, thinking (streamed text, duration, token count), live token
   usage from vLLM's per-chunk usage, tool calls with a structured display subset of their input,
   tool results with stats, the plan (`todo_updated`) and model retries are all events. The
   server sends structured data; the frontend owns the wording. Deltas are coalesced (100 ms) and
   usage is throttled (2 per second).
5. **File content travels in `file_changed`**; `ai-service` flushes to `project-service` in one
   atomic batch per safe point and at the end of the run, announced by `files_persisted`. After
   `run_finished` the frontend reloads the tree from `project-service`, the source of truth.
6. **Preview reports are per project** and name the files they rendered (`basis`: a run and
   `seq`, or a stored revision), with a `settled` flag for late lazy-chunk errors. An active run
   receives them at its next safe point; otherwise they go with the next run.
7. **Request a `files` module from `project-service`** as specified in the
   [requirements](../project-service-contract.md): a files revision separate from `row_version`,
   immutable revisions, atomic batch changes with `If-Match`, revert as a new revision, and a
   lease with TTL and renewal. The revision a run started from is its restore point.
8. **Lease plus optimistic concurrency.** `ai-service` holds a lease for the length of a run and
   sends `If-Match` on every flush. A `412` during a run ends it as `failed`; the agent never
   overwrites someone else's change.
9. **Development does not wait for part (b).** `LocalWorkspace` (M1.4) implements the same
   semantics (revisions, atomic batches, lease) locally, so Phase 1 proceeds and the
   `project-service` adapter is written when the module exists.

Decisions 10–14 settle the questions left open by the first draft (owner, 2026-09-27):

10. **Thinking is summarised in production.** The live token count and "Thought for 12 s ·
    850 tokens" always show; the reasoning text streams only in development and for admin users.
    Raw reasoning can echo the system prompt, skills or untrusted tool output, and it is most of
    the output tokens, so hiding it also lightens the stream. Traces keep it in full.
11. **Sessions are durable from M1.8, not M6.2.** `ai-service` stores each session's messages and
    runs in PostgreSQL. Because `needs_input` ends the run (Decision 2), the next run rebuilds its
    context from the session history; kept in memory, a restart or deploy while the user fills in
    a question form would lose the conversation. The frontend redraws the chat from the same data
    (`GET /v1/sessions/{id}/messages`).
12. **Admission control with a bounded queue.** A fixed number of runs is active at once; beyond
    it runs wait as `queued` and the stream reports their position; a full queue refuses new runs
    at once with `429 queue_full`; a user has at most one active or queued run. Starting values:
    **3–4 active runs** on a 96 GB GPU (ADR-0001: ~36 tok/s each for 3 users; at 16 sessions
    every run slows to ~16 tok/s with a ~12 s TTFT) and a **queue of 20**, both tuned from
    measurements. Letting every run in would slow all of them together; refusing whenever the
    slots are busy would fail users the system could have served a minute later.
13. **`ai-service` authenticates to `project-service` with the gateway's `X-User-Id`.** It calls
    `project-service` directly on the internal network with the `X-User-Id` it received for the
    run, like every other service behind the gateway. It holds no token, so no run fails on token
    expiry. This relies on `project-service` accepting that header only from inside the network.
14. **Publishing is outside the agent.** The agent writes files only; it never publishes or
    changes a Project's lifecycle or visibility, and those actions are not in its tool set. We
    recommend that `project-service` pin a `publishedRevision` at publish time once published
    Projects expose their files (requirements, open question 3).

## Open questions

1. For the `project-service` team: the files module itself, its storage and retention, and the
   `publishedRevision` recommendation ([requirements](../project-service-contract.md#open-questions-for-the-project-service-team)).

## Consequences

- The frontend can build the chat, the step view, the question form and the preview against
  part (a) now. Event types can be added later without breaking it.
- Sessions are in PostgreSQL from M1.8, so Phase 1 already needs a database. Live run state (the
  event log, active runs, the queue) stays in memory in Phase 1; any instance being able to serve
  any stream needs shared state (Redis, M6.1).
- Phase 1 depends on nobody: `LocalWorkspace` stands in for `project-service`. The risk moves to
  the day the adapter is written against the real module; the contract keeps that small.
- `tool_call_started` early and `cached_tokens` depend on what vLLM streams for Qwen3.8; M1.1
  checks both, and the contract already says what happens if they are missing.
- Preview reports arrive for every settled render, including the user's own edits, so the agent
  can be told about a broken preview it did not cause.
