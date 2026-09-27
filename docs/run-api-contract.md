# Run API contract (frontend ↔ `ai-service`)

- **Version:** v1 draft · 2026-09-26 · from M0.4 (ADR-0003)
- **Audience:** the frontend team and the API gateway team; `ai-service` implements it in M1.8.

The frontend talks to `ai-service` through the API gateway. A **run** is one agent turn: it starts
from a user message (or the answers to a question form), streams events while the agent works,
and always ends with exactly one terminal event. A full-site run takes minutes, so runs are
asynchronous: starting one returns at once and progress arrives over Server-Sent Events (SSE).

## Concepts

| Term | Meaning |
|---|---|
| Project | A file tree in `project-service`, identified by `project_id`. |
| Session | The conversation between one user and the agent about one project. It holds the history that later runs build on. `session_id` is opaque and issued by `ai-service`. |
| Run | One agent turn inside a session. At most **one active run per project**. |
| Event | One item of a run's stream, numbered by `seq` (1, 2, 3, … per run). |
| Revision | The version of the project's files the preview rendered (see [Preview reports](#preview-reports)). |

## Run lifecycle

```
POST /v1/runs ──► running ──► run_finished { status }
                    │            done · needs_input · stopped_at_limit · failed · cancelled
                    └── POST /v1/runs/{id}/cancel ──► (next safe point) ──► cancelled
```

- **`needs_input` ends the run.** The agent asked structured questions; the frontend renders a form
  and sends **all answers together** as the input of a new run in the same session. Nothing is
  held open while the user thinks.
- A plain message sent while questions are pending is also accepted; the agent sees that the
  questions went unanswered.
- **Cancellation** takes effect at the next safe point (after a model response or a tool result).
  A tool that was interrupted is reported as `cancelled`, never as success.
- Files the agent wrote before a cancellation or failure are kept and can be reverted to the
  revision the run started from (`run_started.base_revision`; see the
  [`project-service` contract](project-service-contract.md#4-revert)).

## Endpoints

All paths are behind the gateway. The gateway authenticates the user and forwards `X-User-Id`;
`ai-service` trusts that header only from the gateway. Request and response bodies are JSON
(UTF-8) unless stated otherwise.

| Method and path | Purpose |
|---|---|
| `POST /v1/runs` | Start a run. |
| `GET /v1/runs/{run_id}/events` | SSE stream of the run's events, with replay. |
| `GET /v1/runs/{run_id}` | Snapshot of the run (status, last `seq`, pending questions). |
| `POST /v1/runs/{run_id}/cancel` | Ask the run to stop. |
| `POST /v1/projects/{project_id}/preview-reports` | Report what the preview rendered. |

### `POST /v1/runs`

Headers: `Idempotency-Key: <uuid>` (required) — retrying with the same key returns the same run
instead of starting a second one.

```json
{
  "project_id": "prj_123",
  "session_id": "ses_456",
  "input": { "kind": "message", "text": "Build a landing page for a coffee roastery" }
}
```

`session_id` is omitted or `null` to open a new session. The answers to a question form use
`kind: "answers"`:

```json
{
  "project_id": "prj_123",
  "session_id": "ses_456",
  "input": {
    "kind": "answers",
    "question_set_id": "qs_789",
    "answers": [
      { "question_id": "site_type", "value": "landing" },
      { "question_id": "sections", "value": ["hero", "menu", "contact"] },
      { "question_id": "tone", "value": "Warm, handmade, a bit playful" }
    ]
  }
}
```

`value` is a string for `single` and `text` questions and an array of option ids for `multi`.

**`202 Accepted`**

```json
{
  "run_id": "run_abc",
  "session_id": "ses_456",
  "status": "running",
  "events_url": "/v1/runs/run_abc/events"
}
```

### `GET /v1/runs/{run_id}/events`

Response `Content-Type: text/event-stream`. Each event is sent as:

```
id: 42
event: file_changed
data: {"seq":42,"run_id":"run_abc","type":"file_changed","ts":"2026-09-26T10:15:03.120Z","data":{…}}

```

- **Replay.** The stream starts after the `Last-Event-ID` header, or after `?after=<seq>`, or from
  the beginning when neither is given. A reconnecting client therefore never loses or duplicates
  an event. `EventSource` sends `Last-Event-ID` on its own when it reconnects.
- **Heartbeat.** A comment line `: ping` every **15 s**. A single model call can stay silent for
  more than 13 s at long context (ADR-0001), so without it idle-timeouts would cut the stream.
- The server **closes the stream after `run_finished`**. Closing or losing the stream does **not**
  cancel the run.
- Events stay available for replay for **1 hour** after the run ends. After that the endpoint
  returns `410 events_expired`; use `GET /v1/runs/{run_id}` and reload files from
  `project-service`.

### `GET /v1/runs/{run_id}`

```json
{
  "run_id": "run_abc",
  "session_id": "ses_456",
  "project_id": "prj_123",
  "status": "needs_input",
  "last_seq": 318,
  "questions": { "question_set_id": "qs_789", "items": [ … ] },
  "started_at": "2026-09-26T10:14:51.004Z",
  "finished_at": "2026-09-26T10:15:40.771Z"
}
```

`status` is `running` or one of the terminal statuses; `questions` is present only for
`needs_input`.

### `POST /v1/runs/{run_id}/cancel`

Empty body. **`202 Accepted`**; the stream later delivers `run_finished` with `status:
"cancelled"`. Cancelling a finished run is a no-op that returns `202` as well.

## Events

The stream shows the agent working step by step, the way a coding-agent CLI does: which step it
is on, that it is thinking and for how many tokens, which tool it is calling and on what, what
the tool returned, and its plan. The frontend renders these facts; `ai-service` sends structured
data rather than display strings, so the wording and language stay in the frontend.

Every event has the envelope `{ seq, run_id, type, ts, data }`. A **step** is one model call plus
the tool calls it made, numbered from 1. A typical step streams:

```
step_started
  thinking_started · thinking_delta … · usage … · thinking_finished
  message_delta …
  tool_call_started · tool_call · file_changed? · tool_result      (per tool call)
  todo_updated?
step_finished
```

### Run

| `type` | `data` | Notes |
|---|---|---|
| `run_started` | `{ session_id, project_id, base_revision }` | Always `seq` 1. `base_revision` is the `project-service` revision the run started from. |
| `run_finished` | `{ status, reason?, questions?, revision?, usage }` | Always the last event. See [below](#run_finished). |

### Steps and model output

| `type` | `data` | Frontend shows, e.g. |
|---|---|---|
| `step_started` | `{ step, max_steps }` | "Step 3 of 40" |
| `thinking_started` | `{ step }` | "Thinking…" |
| `thinking_delta` | `{ step, text }` | The reasoning text, collapsible. Not sent when thinking display is off (below). |
| `thinking_finished` | `{ step, duration_ms, tokens }` | "Thought for 12 s · 850 tokens" |
| `message_delta` | `{ step, text }` | Assistant text for the user. |
| `usage` | `{ step, input_tokens, output_tokens, cached_tokens?, run_input_tokens, run_output_tokens }` | A live token counter. `input_tokens` is the current model call's prompt; `output_tokens` is what it has generated so far; `run_*` are totals for the run. `cached_tokens` appears when the model server reports prefix-cache hits. |
| `model_retry` | `{ step, attempt, max_attempts, delay_ms, reason }` | "Model connection lost, retrying (1/2)…" |
| `step_finished` | `{ step, duration_ms, finish_reason }` | Collapses the step. `finish_reason` ∈ `tool_calls`, `stop`, `length`. |

Token counts come from the model server's per-chunk usage (vLLM `stream_options:
{ include_usage, continuous_usage_stats }`). `thinking_finished.tokens` is the number of output
tokens generated before the first answer or tool-call token of that step.

### Tools

| `type` | `data` | Frontend shows, e.g. |
|---|---|---|
| `tool_call_started` | `{ step, call_id, name }` | "Writing…" as soon as the model has chosen the tool, while its arguments are still being generated. |
| `tool_call` | `{ step, call_id, name, input }` | "Reading `app/page.tsx` (lines 1–120)". `input` is the display subset below. |
| `tool_result` | `{ step, call_id, status, duration_ms, stats?, error? }` | "Read 120 lines · 45 ms". `status` ∈ `ok`, `error`, `cancelled`; `error` = `{ code, message }`. |
| `todo_updated` | `{ items: [{ content, status }] }` | The plan as a checklist; `status` ∈ `pending`, `in_progress`, `completed`. The full list is sent every time. |

`tool_call_started` is sent early only if the model server streams the tool name before the
arguments (verified in M1.1); otherwise it is sent together with `tool_call`.

`input` and `stats` per tool. Large arguments (file contents, `old_string`/`new_string`) are
never sent here; the result of a write arrives as `file_changed`.

| Tool | `input` | `stats` |
|---|---|---|
| `Read` | `{ path, offset?, limit? }` | `{ lines, truncated }` |
| `Write` | `{ path, bytes }` | `{ bytes }` |
| `Edit` | `{ path, replace_all }` | `{ replacements }` |
| `Glob` | `{ pattern, path? }` | `{ matches }` |
| `Grep` | `{ pattern, path?, glob? }` | `{ matches, files }` |
| `TodoWrite` | `{ items }` (count) | – (the list arrives as `todo_updated`) |
| `ask_user` | `{ questions }` (count) | – (the questions arrive in `run_finished`) |

Tools added later (skills, `check_preview`, MCP) define their `input` and `stats` when they
land. A tool the frontend does not know is shown by `name` only.

### Files

| `type` | `data` | Notes |
|---|---|---|
| `file_changed` | `{ path, op, content?, sha256? }` | `op` ∈ `create`, `update`, `delete`. `content` (full UTF-8 text) and `sha256` are present unless `op` is `delete`. Sent as soon as the agent writes, so the preview updates live. |
| `files_persisted` | `{ revision, paths }` | The listed changes are stored in `project-service` as `revision`. Sent at safe points and before `run_finished`. |

### `run_finished`

| Field | Meaning |
|---|---|
| `status` | `done`, `needs_input`, `stopped_at_limit`, `failed` or `cancelled`. |
| `reason` | Human-readable detail for `stopped_at_limit`, `failed` and `cancelled`. |
| `questions` | For `needs_input`: `{ question_set_id, items: [{ id, text, kind, options?, required }] }` with `kind` ∈ `single`, `multi`, `text` and `options` = `[{ id, label }]`. |
| `revision` | The last `project-service` revision the run wrote, if it wrote any. |
| `usage` | `{ steps, input_tokens, output_tokens, thinking_tokens, duration_ms }`. |

### Stream volume

- `thinking_delta` and `message_delta` are coalesced: at most one event per stream every
  **100 ms**.
- `usage` is sent at most **twice per second** while the model generates, and once at the end of
  every model call.
- **Thinking display** is a server setting. When it is off, `thinking_delta` is not sent;
  `thinking_started` and `thinking_finished` still are, so "Thought for 12 s" still shows. Raw
  reasoning can echo parts of the system prompt; whether production shows it is an owner decision
  (ADR-0003).

### Rules for the client

1. **Ignore unknown event types and unknown fields.** New ones are added without a version bump.
2. Group events by `step`, and tool events by `call_id`.
3. Apply `file_changed` events in `seq` order to the preview's file set.
4. **After `run_finished`, reload the file tree from `project-service`.** It is the source of
   truth; this also repairs the preview if `ai-service` failed between a `file_changed` and the
   next `files_persisted`.
5. During a run the project is leased to `ai-service`: the editor is read-only, and user writes to
   `project-service` are rejected. The user can cancel the run to edit.

## Preview reports

The frontend reports what the preview rendered **every time a render settles** — during a run and
also after the user's own edits. `ai-service` uses the reports for the self-fix loop (M2.7): an
active run receives them at its next safe point; otherwise the latest report is attached to the
next run in that project.

### `POST /v1/projects/{project_id}/preview-reports`

```json
{
  "basis": { "kind": "run", "run_id": "run_abc", "seq": 57 },
  "settled": true,
  "route": "/menu",
  "bundler_errors": [
    {
      "title": "ModuleNotFoundError",
      "message": "Cannot find module '@/components/Menu' relative to '/app/menu/page.tsx'",
      "path": "/app/menu/page.tsx",
      "line": 3,
      "column": 1
    }
  ],
  "runtime_errors": [
    {
      "kind": "react.render",
      "message": "boom during render",
      "stack": "…",
      "component_stack": "…"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `basis` | Which files were rendered: `{ kind: "run", run_id, seq }` = the project as of that run's event `seq` (the last `file_changed` applied), or `{ kind: "revision", revision }` = a stored `project-service` revision. |
| `settled` | `true` once the bundler is idle and the lazy-chunk window has passed (at least ~10 s when `next/dynamic` is used — ADR-0002 Decision 3). An unsettled report may be sent earlier and followed by a settled one. |
| `route` | The URL path shown in the preview. |
| `bundler_errors` | Sandpack `show-error` messages, shape as in the [preview contract](preview-contract.md#error-reports-the-preview-produces). |
| `runtime_errors` | Bridge reports; `kind` ∈ `window.error`, `unhandledrejection`, `react.render`, `react.uncaught`. `[preview contract]` shim errors arrive here. |

An empty pair of error lists means the render succeeded. **`202 Accepted`**. Limits: body ≤ 64 KB;
the frontend truncates stacks to their first 40 lines and sends at most 20 errors per list.
Screenshots are not part of v1; they are added for M5.4 as a separate upload.

## Errors

Error responses have the body `{ "error": { "code": "...", "message": "..." } }`.

| HTTP | `code` | When |
|---|---|---|
| 400 | `invalid_request` | Malformed body; answers that do not match the pending `question_set_id`. |
| 403 | `forbidden` | The user may not access this project, session or run. |
| 404 | `not_found` | Unknown project, session or run. |
| 409 | `run_active` | The project already has an active run; the body includes its `run_id`. |
| 410 | `events_expired` | Replay requested after the retention window. |
| 423 | `project_locked` | The project is leased by another holder in `project-service`. |
| 429 | `rate_limited` | Gateway or per-user quota (M6.1). |

## Gateway requirements

- Do not buffer `text/event-stream` responses; forward each event as it arrives.
- Idle timeout on SSE connections of **at least 30 s** (twice the heartbeat). A maximum connection
  lifetime is fine: clients reconnect with `Last-Event-ID`.
- `EventSource` cannot set headers, so authentication for the events endpoint must work with a
  cookie (or the frontend uses a fetch-based SSE client).
- Forward `X-User-Id`, `Idempotency-Key` and `Last-Event-ID`; strip any `X-User-Id` sent by the
  client.
- Forward `Authorization` as well: `ai-service` calls `project-service` on the user's behalf
  (ADR-0003).

## Versioning

The prefix `/v1` changes only for breaking changes. Adding endpoints, event types, optional
fields or error codes is not breaking (client rule 1).
