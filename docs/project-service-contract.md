# `project-service` contract: project files (requirements)

- **Version:** v1 · 2026-09-27 · from M0.4 (ADR-0003); agreed with the `project-service` team
  2026-09-27
- **Audience:** the `project-service` team. `ai-service` implements its side in M1.4
  (`ProjectServiceWorkspace`); the frontend reads files through the same endpoints.
- **Status:** **implemented** in `project-service` (commit `5396dd9`, checked 2026-10-08). The
  design follows the Catalog API's conventions and lives in the same service as a `files` module.
  Where this document and the code differ, [As built](#as-built-2026-10-08) says what the code does;
  the integration guide is [`ref/ai-service-integration.md`](../ref/ai-service-integration.md).
  `ai-service` implements its side as `ProjectServiceWorkspace` (M1.4).

## Why

Catronaut's agent writes a Next.js project into a Catalog Project. The files have to live
somewhere the frontend, the preview and the agent all read from, with history so a run can be
undone, and with a lock so the user and the agent do not overwrite each other. ROADMAP D3 puts
that in `project-service`, next to the Project it belongs to.

| `ai-service` needs | Phase 1 Catalog API | Requested below |
|---|---|---|
| Read the whole file tree with contents | – | [1. Get files](#1-get-files) |
| Write several files atomically | – | [2. Apply changes](#2-apply-changes) |
| A restore point per run, and revert | – (`project_versions` is deferred and means releases) | [3. List revisions](#3-list-revisions), [4. Revert](#4-revert) |
| Keep the user from editing while the agent runs | – | [5–8. Lease](#5-acquire-lease) |
| Optimistic concurrency | `ETag` / `If-Match` / `412` on `row_version` | The same pattern on a separate **files revision** |

## Conventions

Everything from the Catalog API applies unchanged: gateway path `/api/projects`, service paths
without a version prefix, JSON, UUID identifiers, ISO-8601 UTC timestamps, the `ApiResponse<T>`
envelope, stable error codes, `404` for projects the caller may not see.

Additions:

- **Files revision.** Each Project has a `filesRevision`: an integer starting at `0` that grows by
  one with every successful change to its files. It is **separate from `row_version`**, so
  editing the title and writing files never conflict with each other. The files endpoints return
  it as their `ETag` and take it in `If-Match`.
- **Revisions are immutable and kept.** A revision is the complete tree at that point. Storing
  file contents by `sha256` keeps this cheap: a revision that changes one file stores one blob.
- **Files are UTF-8 text.** No binary files (the [preview contract](preview-contract.md) forbids
  them).
- **Paths** are relative, `/`-separated, without `.` or `..` segments, without a leading `/`,
  case-sensitive, at most 300 characters. Brackets and parentheses must be allowed: Next.js uses
  `app/blog/[slug]/page.tsx` and `app/(marketing)/layout.tsx`.
- **Limits** (starting values, adjustable): 512 KB per file, 1,000 files and 10 MB per revision,
  200 changes per request.
- Files can be changed while the Project is `DRAFT` or `PUBLISHED`; `ARCHIVED` and deleted
  Projects reject writes with `PROJECT_INVALID_STATE`.

## 1. Get files

```http
GET /{projectId}/files?include=content
Authorization: Bearer <access-token>
```

`include=content` returns contents; without it only the manifest. `revision=<n>` reads an older
revision.

```json
{
  "revision": 12,
  "files": [
    {
      "path": "app/page.tsx",
      "size": 1834,
      "sha256": "9f2c…",
      "content": "export default function Home() { … }"
    }
  ]
}
```

Success: `200 OK`, `ETag: "12"`, `ApiResponse<FilesResponse>`. A new Project has revision `0` and
no files.

Errors: `400`, `401`, `404`.

## 2. Apply changes

```http
POST /{projectId}/files/changes
Authorization: Bearer <access-token>
If-Match: "12"
Lease-Id: 5d0c…            # required while the Project is leased
Content-Type: application/json
```

```json
{
  "changes": [
    { "op": "PUT", "path": "app/page.tsx", "content": "…" },
    { "op": "PUT", "path": "components/hero.tsx", "content": "…" },
    { "op": "DELETE", "path": "app/old/page.tsx" }
  ],
  "label": "run:run_abc step 4",
  "source": { "kind": "AGENT", "runId": "run_abc" }
}
```

Rules:

- **All or nothing:** either every change applies and the revision grows by exactly one, or
  nothing changes.
- `If-Match` must equal the current `filesRevision`, otherwise `412 FILES_STALE_REVISION` and the
  current revision in the `ETag` header.
- While a lease is active, the request must carry that lease's `Lease-Id`, otherwise
  `423 PROJECT_LEASED`.
- `PUT` creates or replaces; `DELETE` of a missing path is `404 FILE_NOT_FOUND`.
- `label` (≤ 200 characters) and `source` (`USER` or `AGENT`, with `runId` for the agent) are
  stored on the revision for the history list.

Success: `200 OK`, `ETag: "13"`, `ApiResponse<{ revision, files: [{ path, sha256, size }] }>`
listing the changed paths.

Errors: `400`, `401`, `403`, `404`, `409`, `412`, `413`, `423`.

## 3. List revisions

```http
GET /{projectId}/files/revisions?page=0&size=20
Authorization: Bearer <access-token>
```

Newest first, the Catalog API's pagination shape. Each item:

```json
{
  "revision": 13,
  "label": "run:run_abc step 4",
  "source": { "kind": "AGENT", "runId": "run_abc" },
  "changedPaths": 3,
  "createdAt": "2026-09-27T10:15:40Z"
}
```

Errors: `400`, `401`, `404`.

## 4. Revert

```http
POST /{projectId}/files/revert
Authorization: Bearer <access-token>
If-Match: "17"
Lease-Id: 5d0c…            # when leased
Content-Type: application/json
```

```json
{ "toRevision": 12, "label": "Revert run run_abc" }
```

Creates a **new** revision whose tree equals revision 12. History is never rewritten, so a revert
can itself be reverted. The same `If-Match` and lease rules as [Apply changes](#2-apply-changes).

Success: `200 OK`, `ETag: "18"`, `ApiResponse<{ revision }>`.

Errors: `401`, `403`, `404 REVISION_NOT_FOUND`, `409`, `412`, `423`.

## 5. Acquire lease

A lease gives one holder the exclusive right to change a Project's files for a limited time. The
agent takes one for the length of a run.

```http
POST /{projectId}/lease
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{ "holder": "ai-service", "runId": "run_abc", "ttlSeconds": 120 }
```

Success: `201 Created`, `ApiResponse<Lease>`:

```json
{
  "leaseId": "5d0c…",
  "holder": "ai-service",
  "runId": "run_abc",
  "baseRevision": 12,
  "expiresAt": "2026-09-27T10:17:40Z"
}
```

`baseRevision` is the run's restore point: the `filesRevision` when the lease was **first**
acquired for this `runId`; acquiring again for the same run does not move it. When the lease is
released or expires, the current `filesRevision` becomes the run's end point. Both are kept until
the Project is deleted ([follow-up answer 1](#follow-up-answers-2026-09-27)).

Errors: `401`, `403`, `404`, `409 PROJECT_INVALID_STATE`, `423 PROJECT_LEASED` (the body carries
the current lease without its `leaseId`).

## 6. Renew lease

```http
PUT /{projectId}/lease/{leaseId}
Authorization: Bearer <access-token>
```

Extends `expiresAt` by the original TTL. `ai-service` renews every `ttlSeconds / 3`.

Errors: `401`, `404 LEASE_NOT_FOUND` (released or expired).

## 7. Release lease

```http
DELETE /{projectId}/lease/{leaseId}
Authorization: Bearer <access-token>
```

Success: `204 No Content`. Releasing an unknown or expired lease also returns `204`.

## 8. Get lease

```http
GET /{projectId}/lease
Authorization: Bearer <access-token>
```

Returns the active lease (without `leaseId`) or `data: null`. The frontend uses it to show
"Catronaut is editing" and make the editor read-only after a reload.

An expired lease is gone: the next write without `Lease-Id` succeeds. This is what frees the
Project if `ai-service` crashes mid-run.

## New error codes

| Code | HTTP | Meaning |
|---|---:|---|
| `FILE_PATH_INVALID` | 400 | A path breaks the path rules. |
| `FILE_NOT_TEXT` | 400 | Content is not valid UTF-8 text. |
| `FILE_NOT_FOUND` | 404 | `DELETE` of a path that does not exist. |
| `REVISION_NOT_FOUND` | 404 | Unknown revision. |
| `LEASE_NOT_FOUND` | 404 | The lease was released or has expired. |
| `FILES_STALE_REVISION` | 412 | `If-Match` does not match `filesRevision`. |
| `FILES_LIMIT_EXCEEDED` | 413 | A file, revision or request limit was exceeded. |
| `PROJECT_LEASED` | 423 | Another holder has the lease. |

## Authentication for `ai-service`

Catronaut's existing flow: the client sends its access token to the API gateway, the gateway
validates and decodes it and forwards `X-User-Id` to the services behind it, which trust that
header. The `Authorization: Bearer` lines above show the gateway-facing call.

`ai-service` follows the same flow. It receives `X-User-Id` from the gateway with the run request
and calls `project-service` **directly on the internal network with that same `X-User-Id`**, for
every request of the run. `project-service` applies its usual ownership rules to that user; it
needs no new mechanism.

- No token is held by `ai-service`, so a run that lasts minutes cannot fail on token expiry.
- The trust model is the network's: `project-service` must accept `X-User-Id` only from the
  gateway and internal services, and the gateway strips any `X-User-Id` sent by a client.
- `source.kind: "AGENT"` in [Apply changes](#2-apply-changes) marks the agent's writes in the
  history; it is not an authorisation claim.

## How `ai-service` uses the API

```
run start    POST lease                                    → leaseId, baseRevision R0
             GET files?include=content                     → working copy at revision R0
during run   POST files/changes  If-Match: Rn, Lease-Id    → Rn+1   (at each safe point with writes)
             PUT lease/{id}      every ttl/3
run end      POST files/changes  (final flush, label "run:<id> end")
             DELETE lease/{id}
undo a run   POST files/revert   toRevision: R0
```

- R0, the revision the run started from, is its restore point. `project-service` records it with
  the lease and never prunes it.
- A `412` during a run means the lease was lost and someone else wrote. `ai-service` does not
  overwrite: the run ends as `failed` with that reason, and the user sees the other change.
- If `ai-service` crashes, changes since the last safe point are lost and the lease expires
  within `ttlSeconds`. The frontend reloads the tree after the run ends (run API client rule 4).

## Open questions for the `project-service` team

1. Storage: database rows with content-addressed blobs, or object storage (the Catalog blueprint
   already plans object storage for source snapshots)?
2. Retention: keep every revision, or prune intermediate agent revisions after N days and keep
   the labelled run start/end points?
3. Publishing. Publishing stays a user action in the catalog (`DRAFT + PRIVATE` →
   `PUBLISHED + PUBLIC`); the agent never publishes or changes lifecycle or visibility. When
   publishing starts to show the project's files or a live demo, **we recommend pinning a
   `publishedRevision` at publish time**: later agent or user edits then do not change what the
   public sees until the owner publishes again, and a rollback only moves the pointer. This
   belongs with the deferred `project_versions` (Release) work.

## Answers from the `project-service` team (2026-09-27)

1. **Storage.** Split by layer instead of choosing one:
   - **Metadata in Postgres** — not just the `filesRevision` counter, but the whole manifest per
     revision (`path → sha256 → size`). This is the part that must be transactional with the
     revision bump and the `If-Match` check ("all or nothing," [§2](#2-apply-changes)); object
     storage has no cross-key transactions, so the manifest can't live there.
   - **File content in object storage**, keyed by `sha256` (content-addressed, matching "revisions
     are immutable"). Reuses the object storage the Catalog blueprint already plans for source
     snapshots, and files with the same content — across files or across revisions — share one
     blob automatically, which keeps size down against the 512 KB/file, 10 MB/revision limits.
   - This split is invisible to `ai-service`/the frontend: the files API contract above doesn't
     change either way, so the object-storage backend (S3, MinIO, …) can be swapped later without
     touching this contract.

2. **Retention.** Agreed with pruning intermediate agent revisions after N days and keeping
   labelled run-start/run-end points, with one added rule: **never prune a revision still
   referenced** — by the current `publishedRevision` (answer 3), or by a `revision`/`base_revision`
   value stored in session history. Sessions are durable and kept indefinitely
   ([run API contract](run-api-contract.md), ADR-0003 Decision 11), so a user can reopen an old
   session and revert to its `base_revision` long after N days have passed; pure time-based
   pruning would silently break that revert.

3. **Publishing.** Agreed — pin `publishedRevision` at publish time, and treat it as a requirement
   rather than a nice-to-have, not gated on the full `project_versions`/Release work. Without the
   pin, a run in progress on an already-published Project would change what the public sees
   between safe points, which is exactly what ADR-0003 Decision 14 ("the agent never publishes or
   changes lifecycle/visibility") is meant to prevent — a moving `publishedRevision` is an indirect
   way of doing that.

## Follow-up answers (2026-09-27)

1. **Retention vs. run start — OK, with three additions.** `project-service` records the run's
   restore point when `POST /{projectId}/lease` succeeds, and exempts it from pruning. This replaces
   the label-based rule, so nothing depends on how a revision is labelled.
   - **Return it in the lease response** as `baseRevision`: `ai-service` then takes R0 from the
     lease and does not rely on a separate `GET files` returning the same number. While the lease is
     active nobody else can write, so both reads agree, but one source is simpler. Adding a field to
     `Lease` is not breaking.
   - **First acquire per `runId` wins.** If `ai-service` acquires a lease again for the same run,
     the recorded start point does not move.
   - **Record the end point the same way:** when the lease is released or expires, the current
     `filesRevision` becomes that run's end point and is exempt from pruning too. This covers a run
     that failed or crashed before its final flush. Its last revision is labelled `run:<id> step N`,
     not `run:<id> end`, yet `run_finished.revision` still points at it.
   - These are rows of (`projectId`, `runId`, `startRevision`, `endRevision`). They are deleted only
     with the Project. Blobs are shared by `sha256`, so keeping these revisions costs little.

2. **Storage — confirmed.** Blobs are uploaded before the manifest transaction commits, and a GC
   job removes orphaned blobs. How it works:
   - The server computes `sha256` itself and never trusts one sent by a client. An upload whose
     key already exists is skipped, so retries are idempotent.
   - GC is mark-and-sweep with a **grace period** (starting value 24 h). It deletes a blob only
     when no manifest references it **and** the blob is older than the grace period. Without the
     grace period, GC could delete a blob that a transaction still in flight has uploaded but not
     yet committed, or a blob that a new revision is about to reuse.

3. **`publishedRevision` — correct.** It must exist before a published Project exposes files or a
   live demo publicly. Phase 1 Catalog stays metadata-only. One addition for when it lands: existing
   `PUBLISHED` Projects start with `publishedRevision = null`, which means no files are shown
   publicly until the owner publishes again. The migration does not backfill it with the current
   `filesRevision`, because that would publish content without any action by the owner.

## As built (2026-10-08)

What `project-service` actually does, from `ref/ai-service-integration.md`. Only the differences
and additions to the sections above are listed; the rest matches.

- **Header.** `X-User-ID` (header names are case-insensitive, so `X-User-Id` works too), sent on
  the direct internal call. Paths have no `/api/projects` prefix. Every endpoint except `GET
  /files` on a public published project requires the owner (`403` otherwise).
- **Lease.** `holder` 1..100 characters, `runId` 1..200, `ttlSeconds` 30..3600 (default 120).
  `leaseId` is returned only by acquire and renew. Acquiring while any lease exists, the same run's
  included, is `423 PROJECT_LEASED`: renew instead. `baseRevision` is still fixed by the run's
  first acquire.
- **`If-Match`.** A quoted number (`"12"`); missing or unquoted is `400 VALIDATION_FAILED`. Take it
  from the `ETag` of `GET /files`, never from `baseRevision`, which stays at the run's start.
- **Checks on a write run in this order:** owner and state, revision (`412`), lease (`423`), then
  the payload. A stale `If-Match` is reported even when the lease is also wrong.
- **Paths** also forbid `:` and NUL, and a path cannot be both a file and a directory (`app` vs
  `app/page.tsx`). Content is UTF-8 without NUL. A path appears at most once per batch.
- **`503 FILES_STORAGE_UNAVAILABLE`.** Object storage failed and nothing was committed; retry with
  the same `If-Match`.
- **The lease is enforced only while it exists.** After it expires, a write with the right
  `If-Match` is accepted and the old `Lease-Id` ignored, so `ai-service` stops writing itself as
  soon as a renewal returns `404`.
- **Revert** has no `source`; it is always recorded as `USER`.
- **The run's end revision** is stored (`project_file_run_checkpoints`) but not exposed over HTTP
  yet; `ai-service` tracks the revisions its own saves return.
- **Decision kept (ADR-0003 Decision 8).** The integration guide suggests re-reading the tree after
  a `412`. Under our lease a `412` means someone else wrote, so `ai-service` ends the run as
  `failed` and does not retry.
