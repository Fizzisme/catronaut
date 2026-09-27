# ADR-0004 — Static verification: tree-sitter rules plus a type-check sidecar

- **Status:** Accepted 2026-09-27. The owner accepted the type-check sidecar (Decision 2) and the
  preview-contract update (Decision 4).
- **Milestone:** M0.5 (ROADMAP §7, Phase 0)
- **Feeds:** M2.6 (build and verify), M6.5 (export fidelity)

## Context

The preview is more permissive than Next.js ([ADR-0002](0002-preview-runtime.md), Consequences):
Node APIs, `"use server"`, route handlers and nested async components render in the browser and
then fail `next build`. The [preview contract](../preview-contract.md) marks these rules
"Enforced by M0.5". D2 settles that TSX is verified parse-only with tree-sitter, and that a Node
type-check sidecar is added only if evaluation shows parse-only lets too many errors through.
D5 forbids building or running generated code in `ai-service`.

This spike had to answer:

1. Can a tree-sitter verifier enforce the contract without false positives on valid projects?
2. Which errors slip through parse-only, and would a type checker catch them?
3. What does each layer cost per check?

## Measurement setup

| Item | Value |
|---|---|
| Verifier | `evals/spikes/m0_5/verifier.py`: `tree-sitter` 0.26.0 and `tree-sitter-typescript` 0.23.2 (TSX grammar for `.tsx/.jsx/.js`, TypeScript grammar for `.ts`) |
| Baseline | `tsc --noEmit` from TypeScript 5.9.3 against `next` 16.0.0, `@types/react` 19.2.18, `@types/node` 22 and every vetted package, installed once with `--ignore-scripts`; the case's own `tsconfig.json` extended with what `create-next-app` adds (`skipLibCheck`, `isolatedModules`, `next-env.d.ts`) |
| Corpus | 60 projects: the M0.3 `starter`, 4 `deps/*` and 13 `errors/*` fixtures, plus 42 seeded cases in `evals/spikes/m0_5/corpus/<layer>/`, each overlaying one file or two on the starter |
| Driver | `evals/spikes/m0_5/run_corpus.py`, 4 parallel `tsc` processes |
| Machine | Windows 11 laptop (same as M0.3) |

Every case names the **layer** expected to catch it: `static` (a contract rule this verifier
must enforce), `typecheck` (only a type checker can see it), `build` (only `next build` or
server rendering reveals it), `runtime` (only the preview reveals it), `clean` (a valid project).

## The rules

| Rule | Catches | Contract row |
|---|---|---|
| `parse.syntax` | tree-sitter `ERROR` / `MISSING` nodes | — |
| `parse.jsx-mismatch` | `<h1>…</h2>`: **tree-sitter accepts it without an error node** | — |
| `import.unresolved` | relative and `@/` imports (via `tsconfig.json` `paths`) that match no file | — |
| `import.missing-export` | named or default import that the local target does not export | — |
| `package.undeclared` | bare import missing from `package.json` `dependencies` | Project shape |
| `package.not-vetted` / `package.on-hold` / `package.version` | dependency outside the vetted list, on hold (GSAP), or not pinned to the vetted version | Vetted dependencies |
| `module.forbidden` | `next/headers`, `next/server`, `next/cache`, `next/og`, `next/script`, `next/font/local`, `server-only`, Node built-ins (`fs`, `node:*`, …), `next/*` entry points without a shim (`next/router`) | Forbidden |
| `module.static-asset` · `file.binary` | image/font/video imports; binary or non-UTF-8 files | Project shape |
| `file.forbidden-route` | `app/**/route.ts`, `middleware.ts`, `proxy.ts` | Forbidden |
| `file.unsupported-convention` | `loading`, `error`, `global-error`, `template`, `default`, `@slot`, `(.)` segments | Project shape |
| `directive.use-server` | `"use server"` at file or function level | Forbidden |
| `export.server-feature` | `generateStaticParams`, `generateMetadata`, `revalidate`, `dynamic`, … exported under `app/` | Forbidden |
| `fetch.own-api` | `fetch("/…")` to our own API routes | Forbidden |
| `env.process` | `process.env.X` other than `NODE_ENV` | Forbidden |
| `component.nested-async` | an `async` function returning JSX that is not the default export of a page or layout | Forbidden |
| `three.environment-preset` | drei `<Environment preset|files>` | Forbidden |
| `layout.root-html` | root layout missing, or not rendering `<html>` and `<body>` | Project shape |
| `image.src` | `next/image` `src` that is a local path, or a host not in `next.config` `images.remotePatterns` | Allowed (`next/image`) |
| `client.boundary` | in a module reached from a page/layout **without crossing `"use client"`**: hooks other than `use`, `useId`, `useMemo`, `useCallback`; `createContext`; `on*` props on DOM elements; inline functions passed to a Client Component | Allowed (`"use client"`) |
| `client.dynamic-ssr-false` | `dynamic(…, { ssr: false })` in such a Server Component | Allowed (`next/dynamic`) |

The last four come from this spike: the preview renders them fine, and `next build` fails
(`client.*`) or the image does not load (`image.src`). `client.boundary` walks the import graph
from the app entries and stops at `"use client"` modules, the same boundary Next.js draws.

## Results

### Coverage by layer

| Layer | Cases | Static caught | tsc caught | Static only | tsc only | Neither |
|---|---|---|---|---|---|---|
| static | 40 | **40** | 9 | 31 | 0 | 0 |
| typecheck | 12 | 0 | **12** | 0 | 12 | 0 |
| build | 2 | 0 | 0 | 0 | 0 | 2 |
| runtime | 2 | 0 | 0 | 0 | 0 | 2 |

**False positives on the 4 clean projects** (starter, `deps/motion`, `deps/ui-utils`,
`errors/async-page`): static 0, tsc 0. No static case raised a rule it was not seeded with.

- **tsc cannot replace the verifier.** It caught 9 of the 40 contract cases (syntax, unresolved
  imports, missing exports, uninstalled packages) and none of the other 31: `"use server"`,
  Node APIs (with `@types/node`, as in every real project), route files, server exports and the
  client boundary are all valid TypeScript.
- **Parse-only cannot replace tsc.** All 12 type errors slipped through the verifier:

| Case | tsc | Expected in the preview (not run in M0.5) |
|---|---|---|
| `prop-type` — `count="3"` to a `number` prop | TS2322 | silent |
| `missing-prop` | TS2741 | silent |
| `property-typo` — `post.titel` | TS2551 | silent: empty heading |
| `params-not-awaited` — `params.slug` on a promise | TS2339 | silent: **every post 404s** |
| `possibly-undefined` — no `notFound()` guard | TS18048 | crash only for unknown slugs |
| `link-missing-href` — `<Link to>` | TS2322 | silent: link without `href` |
| `image-missing-alt` | TS2741 | silent |
| `state-type` — string into number state | TS2345 | silent: renders `011…` |
| `undefined-identifier` | TS2552 | ReferenceError |
| `wrong-package-export` — `useState` from `react-dom` | TS2305 | TypeError |
| `await-in-sync` | TS1308 | Babel error (tree-sitter parses it) |
| `duplicate-declaration` | TS2451 | Babel error (tree-sitter has no scopes) |

  About 8 of 12 would be **silent** in the preview, so the self-fix loop (M2.7) never hears of
  them. All 12 fail `next build`, which type-checks by default, so every one of them breaks export.
- **Neither layer sees the `build` cases**: `window.innerWidth` in a Server Component, and
  `localStorage` read during a Client Component's render. Both run fine in the browser and throw
  during server prerendering.

### Cost per project

| Layer | Median | Max |
|---|---|---|
| Static verifier (whole project, in process) | 3.6 ms | 8.3 ms |
| `tsc --noEmit`, fresh process, warm disk cache | 2.2 s | 3.1 s |
| `tsc --noEmit`, first run after install (4 in parallel) | — | 17.8 s |

### What these numbers do not say

- **40/40 is a floor, not a recall estimate.** The same author wrote the rules and the seeded
  cases, so the static layer was bound to catch its own corpus. It shows the rules work and do not
  misfire on valid projects. How often real model output breaks each rule is measured on real runs
  (M2.6, M3 evaluation).
- The corpus has one to three cases per rule, and only two `build` cases.
- Preview behaviour of the `typecheck` cases is predicted from how the M0.3 runtime works, not
  run.
- Package-level client-only APIs are not modelled: `motion`'s entry has no `"use client"`, so
  whether `<motion.div>` in a Server Component fails `next build` needs a real build to answer.

## Decision

1. **The tree-sitter verifier is the always-on verifier** for M2.6, run after every write. It
   costs milliseconds, enforces the contract rules nothing else sees, and M2.6 promotes
   `verifier.py` into `app/domains/ui_ux/` with findings returned as structured tool observations.
2. **Add a Node type-check sidecar** (accepted by the owner, 2026-09-27). Parse-only let 12 of 12 type
   errors through, about two thirds of them silently. Shape:
   - a separate small Node process or container, reachable only from `ai-service`;
   - a fixed, pre-installed `node_modules` of `next`, `typescript`, `@types/*` and the vetted
     packages, installed with `--ignore-scripts` and versioned with the vetted list;
   - it writes its own `tsconfig` (strict, `noEmit`) and keeps only the project's `paths` from
     the agent's; it never honours the agent's `extends` or `plugins`;
   - it runs `tsc --noEmit` with a timeout and a memory cap. It emits nothing and runs nothing, so
     D5 holds: type-checking reads the code like the parser does;
   - it runs at verification points (end of a plan step, before `done`), not after every write,
     because a check costs about 2–3 s;
   - it sits behind a feature switch (principle 5). If M2/M3 evaluation shows it rarely fires on
     real model output, it is removed.
3. **The `build` layer is left to M6.5**, whose CI `next build` measures how often it occurs. If
   it is frequent, a static rule for browser globals (`window`, `document`, `localStorage`,
   `navigator`) read during render, outside effects and handlers, is the next candidate.
4. **The preview contract gains the rules found here** (done in contract v2): the client boundary
   (hooks, event props, function props, `createContext`), `dynamic(…, { ssr: false })` only
   inside `"use client"` files, `next/image` without local paths, and unshimmed `next/*` entry
   points.

## Alternatives considered

| Option | Why not |
|---|---|
| Parse-only, relying on preview reports for the rest | About 8 of the 12 type errors never produce a preview error; they surface only at export. |
| tsc only | Misses 31 of the 40 contract cases. |
| Long-lived TypeScript language service instead of `tsc` per check | Probably much faster per check (incremental), but more to build and operate. Revisit if the 2–3 s cost matters. |
| `next build` in `ai-service` | Violates D5: `next build` runs code (config, prerendering). It belongs in the offline pipeline (M6.5). |

## Consequences

- M2.6 gets two verifiers with different cost profiles; the agent loop calls the static one after
  every write and the type check at verification points.
- A Node service is added to the deployment (if Decision 2 is accepted), and its `node_modules` is
  upgraded together with the vetted list. Type-checking untrusted code can still be made slow on
  purpose (pathological types), hence the timeout and memory cap.
- Rule messages double as tool observations; every finding carries path, line and a fix hint.
- **`next` 16.0.0 has a published security advisory** (npm flags CVE-2025-66478). The M0.3
  starter pins it; the starter version is chosen in M2.2 and must be a patched release.

## Pitfalls met while measuring

- tree-sitter's error recovery is lenient: mismatched JSX tags, `await` in a non-async function
  and duplicate `const` declarations produce no `ERROR` node. Only the first gets a dedicated rule.
- `use(params)` is legal in a Server Component; the hook rule allows the hooks React's server
  build exports (`use`, `useId`, `useMemo`, `useCallback`, `useDebugValue`).
- Type-only imports (`import type`, or every specifier marked `type`) are erased, so package
  rules skip them.
- The M0.3 `deps/three-r3f` fixture uses `<Environment preset>`, which the contract later
  forbade; the verifier reports it.
- The first `tsc` runs take about 18 s while the OS disk cache warms up; later runs take 2–3 s.

## How to re-run

```bash
cd evals/spikes/m0_5/tsc && npm ci --ignore-scripts && cd ../../../..
uv run python -m evals.spikes.m0_5.run_corpus            # add --no-tsc for the verifier only
```

Results land in `m0_5_results/` (`results.json`, `summary.md`).
