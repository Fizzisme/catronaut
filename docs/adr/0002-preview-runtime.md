# ADR-0002 — Preview runtime: Next.js subset on the Sandpack classic bundler

- **Status:** Accepted 2026-09-26. The owner chose to self-host the bundler (open question 1
  settled); the GSAP licence question stays open (see [Open questions](#open-questions)).
- **Milestone:** M0.3 (ROADMAP §7, Phase 0)
- **Hands over to:** the frontend team (owner of the preview runtime, ROADMAP A5), together with
  the [preview contract](../preview-contract.md).

## Context

D1 settles that the agent writes a real Next.js App Router project and that the user sees it
running in the browser on the Sandpack **classic** bundler, because the Nodebox-based `nextjs`
template is pinned to Node 16 and needs a commercial licence (F1). The classic bundler only knows
React, so Next.js has to be emulated. Before building on that, this spike had to answer:

1. Can App Router conventions (`app/**/page.tsx`, nested `layout.tsx`, `[slug]`, route groups,
   `not-found.tsx`, `metadata`) and the `next/*` modules the agent uses be shimmed well enough?
2. Do Tailwind v4 and the creative-layer libraries (motion, gsap, lenis, three / R3F) run?
3. Can bundler and runtime errors be captured and fed back to the agent (M2.7)?
4. Can the preview be screenshotted (M3.3 evaluation, M5.4 visual self-review)?
5. Can the bundler be self-hosted, and under what licence?

## Measurement setup

| Item | Value |
|---|---|
| Harness | `evals/spikes/m0_3/harness/` — Vite + TypeScript host page, `@codesandbox/sandpack-client` 2.19.8, template `create-react-app-typescript` |
| Driver | `evals/spikes/m0_3/run_fixtures.py` — Playwright 1.63 (Python), Chromium headless shell 153, 1280×800 |
| Fixtures | `evals/spikes/m0_3/fixtures/`: `starter` + 13 error cases + 4 dependency trials (18) |
| Bundler A | CodeSandbox-hosted: `https://2-19-8-sandpack.codesandbox.io/` |
| Bundler B | Self-hosted: LibreChat-AI/codesandbox-client release `bundler-v12` (2025-03-07), `bundler.zip` sha256 `e6ce913b…a654c6`, 99 MB unpacked, served by a static file server |
| Machine | Windows 11 laptop, residential connection (Vietnam) |

"Cold" is a fresh browser context (empty browser cache); CodeSandbox's npm packager CDN was
already warm for these dependency sets after the first run. "Warm" reloads the same fixture in
the same context. Times are milliseconds from the host page's start to the preview's first
React commit.

## How the emulation works

`src/translate.ts` turns the project into Sandpack files; the agent's files are passed through
unchanged apart from Tailwind CSS.

- **`next` is a fake package** in `/node_modules/next/**` (`link`, `image`, `navigation`,
  `dynamic`, `font/google`, `font/local`, and throwing modules for `headers`, `server`, `cache`,
  `og`, `script`); `server-only` likewise. Sandpack resolves files under `/node_modules` before
  fetching from npm, so **imports are never rewritten** and the exported project stays a plain
  Next.js project. `next` is dropped from the preview's `dependencies`.
- **A hidden entry** (`/__catronaut/entry.tsx`) imports every page, layout and `not-found` and
  calls `mount()` with a route table: route groups removed from the URL but kept for layout
  lookup, `[x]`, `[...x]` and `[[...x]]` segments, static before dynamic before catch-all.
- **The runtime** (`next/dist/catronaut/runtime.js`) renders with `createRoot(document)`, so the
  root layout's `<html>`/`<body>` attach to the real document (React 19 singletons). A History-API
  router backs `Link`, `useRouter`, `usePathname`, `useSearchParams`, `useParams`, `notFound()` and
  `redirect()`. `params`/`searchParams` are passed as pre-settled promises, so `use(params)` does
  not suspend. An `async` page or layout is called once per URL and its promise is cached and
  read with `use()`. `metadata` (including `title.template`) becomes React 19 `<title>`/`<meta>`.
- **Tailwind v4**: a CSS file containing `@import "tailwindcss"` is moved into a
  `<style type="text/tailwindcss">` (without the import line) for `@tailwindcss/browser` 4.3.3,
  loaded as an external resource. `@theme` and `@apply` work.
- **`next/font/google`** loads the family from the Google Fonts CSS API and returns the Next.js
  `{ className, variable, style }` shape.
- **A bridge** (`/__catronaut/bridge.js`, imported first) posts runtime errors
  (`window.onerror`, `unhandledrejection`, React error boundaries) and render events to the host,
  and answers screenshot requests with `modern-screenshot` 4.7.0.

## Results

### Behaviour — 18/18 fixtures pass on both bundlers

`starter` passes all 16 checks on both bundlers: home heading, title from `metadata`, Tailwind
theme colour, `next/font` variable, `next/image fill`, client state, `Link` to `/about` with a
real pathname, `title.template`, `[slug]` via `use(params)`, route group and its layout, history
back, `notFound()` → `not-found.tsx`, unknown route → `not-found.tsx`, `router.push` with
`useSearchParams`. The `@/*` path alias from `tsconfig.json` resolves without help.

| Fixture | What happens in the preview | Caught? |
|---|---|---|
| `errors/syntax` | Bundler error with file, line and column. The message is wrapped in `TypeError: Cannot assign to read only property 'message'`, but the original Babel text is inside. | Yes |
| `errors/missing-import` | `ModuleNotFoundError … '@/components/does-not-exist' relative to '/app/about/page.tsx'` | Yes |
| `errors/undeclared-package` | `DependencyNotFoundError: 'canvas-confetti'` — packages must be in `package.json` | Yes |
| `errors/render-throw` | Route boundary shows the stack, layout survives, `react.render` error reported | Yes |
| `errors/unhandled-rejection` | Reported by both the bundler and the bridge | Yes |
| `errors/next-headers`, `errors/server-only`, `errors/font-local` | Shim throws a `[preview contract] …` message naming the module | Yes |
| `errors/async-page` | `async` page with `await params` renders correctly | n/a |
| `errors/async-component` | A **nested** async component renders, but React warns ("async Client Component", "uncached promise") and re-runs it on every render | Warning only |
| `errors/node-api` | `import { readFileSync } from "fs"` **silently works** (the bundler polyfills `fs` with BrowserFS) | **No** |
| `errors/use-server` | `"use server"` is ignored; the action **silently runs in the browser** | **No** |
| `errors/route-handler` | `app/**/route.ts` is skipped and listed in the translation notes | Note only |

The three silent cases are exactly what the static verifier (M0.5) must reject.

### Dependency trials

| Fixture | Packages | Result |
|---|---|---|
| `deps/motion` | `motion` 13.4.4 (`motion/react`, `useScroll`) | Renders, no errors |
| `deps/gsap-lenis` | `gsap` 3.15.0 + ScrollTrigger, `@gsap/react` 2.1.2, `lenis` 1.3.26 (`lenis/react`) | Renders, no errors |
| `deps/three-r3f` | `three` 0.186.1, `@react-three/fiber` 9.8.1, `@react-three/drei` 10.7.9 through `next/dynamic` | Renders after a polyfill (below); the canvas appears ≈ 5–6 s after the first render |
| `deps/ui-utils` | `lucide-react` 1.48.0, `clsx` 2.1.1, `tailwind-merge` 3.7.0 | Renders, no errors |

`three` ≥ 0.18x ships `build/three.cjs` that calls `process.emitWarning()`. The classic bundler
resolves the CommonJS entry and its `process` polyfill lacks that function, so the import crashed
until the bridge added a no-op `process.emitWarning`. The crash happened ~6 s after the first
render, inside the lazy chunk; the first driver version stopped listening after 3 s and reported a
clean pass. **Errors from lazy chunks arrive late**, which matters for M2.7's timeout.

### Timing (first React commit, ms)

| | Hosted bundler | Self-hosted bundler |
|---|---|---|
| Cold, 12 rendering fixtures | median **2,088** (1,752–2,840) | median **1,568** (1,453–2,885) |
| Warm | median **703** (max 1,495) | median **796** (max 1,592) |
| Bundler error reported (7 failing fixtures) | 1,466–2,442 | 1,176–1,826 |
| In-iframe screenshot (`modern-screenshot`) | median 199, max 275 | median 215, max 296 |

The very first run of the spike, with CodeSandbox's packager cold for this dependency set, took
4.9 s. The self-hosted bundler saves the iframe load from CodeSandbox (~0.5 s on this connection).

### Screenshots

Both paths produce the same image once two fixes are in:

- **Playwright element screenshot** of the iframe works cross-origin; it is the path for the
  evaluation pipeline (M3.3).
- **In-iframe capture** (`modern-screenshot`, answering a `postMessage` request) is the only path
  the frontend has in production, since the host page cannot read a cross-origin iframe. It lost
  the Google fonts until the font `<link>` got `crossorigin="anonymous"`, and painted the area
  below a short page black until `backgroundColor` was passed. WebGL was captured with
  `preserveDrawingBuffer: true` on the R3F canvas; capture without it was not tested.

### External hosts contacted

| Host | Hosted | Self-hosted | Why |
|---|---|---|---|
| `2-19-8-sandpack.codesandbox.io` | ✓ | – | the bundler itself |
| `prod-packager-packages.codesandbox.io` | ✓ | ✓ | **npm packages, even when self-hosted** |
| `cdn.jsdelivr.net`, `data.jsdelivr.com` | ✓ | ✓ | Tailwind browser build; npm fallback |
| `col.csbops.io`, `static.cloudflareinsights.com` | ✓ | – | CodeSandbox telemetry / analytics |
| `fonts.googleapis.com`, `fonts.gstatic.com` | ✓ | ✓ | `next/font/google` shim |
| `images.unsplash.com` | ✓ | ✓ | fixture images |
| `raw.githack.com`, `raw.githubusercontent.com` | ✓ | ✓ | drei `<Environment preset>` HDR files |

### Licences

| Component | Licence | Verdict |
|---|---|---|
| `@codesandbox/sandpack-client` (host side) | Apache-2.0 | Free to use |
| Bundler (`codesandbox-client`, and the LibreChat build of it) | **GPLv3**, except `packages/common`, `packages/sandpack-core`, `packages/app/src/sandbox` (Apache-2.0). The sandbox entry imports `sandbox-hooks`, which is not in the Apache list, so the build contains GPLv3 code. | Self-hosted under GPLv3 obligations (Decision 5) |
| `@tailwindcss/browser`, `modern-screenshot`, `motion`, `lenis`, `three`, R3F, drei, `clsx`, `tailwind-merge`, `react` | MIT (`lucide-react`: ISC) | Free to use |
| `gsap`, `@gsap/react` | GSAP Standard License: free for commercial use, but "Prohibited Uses" include use "in tools that allow users to build visual animations without code"; its FAQ says "AI-generated code is not a Prohibited Use". | **Open question 2** |

## Decision

1. **Adopt the emulation above** as the reference implementation of the preview runtime and hand
   `evals/spikes/m0_3/harness/src/` to the frontend team with the preview contract. Imports stay
   untouched; `next` and `server-only` are shims in a fake `node_modules`.
2. **The [preview contract](../preview-contract.md) is the agent's rule set**, and M0.5 must
   enforce statically the rules the preview cannot: Node built-ins, `"use server"`, route
   handlers, nested async components.
3. **Error feedback for M2.7** combines Sandpack's `show-error` messages (module path, line,
   column) with the bridge's runtime reports. A report is not final at the first render: wait for
   lazy chunks to settle (at least ~10 s when `next/dynamic` is used, or until the bundler is idle
   with no pending chunk).
4. **Screenshots:** Playwright for evaluation; in-iframe `modern-screenshot` for the product.
5. **Bundler hosting: self-host** (owner decision, 2026-09-26). The self-hosted build passed 18/18
   and was slightly faster than the hosted one. Obligations and limits that come with it:
   - the build is GPLv3: serve it **unmodified**, keep its `LICENSE`, and publish where its
     corresponding source can be obtained (the upstream repository and release tag). Any change to
     the bundler must be published under GPLv3 as well. This is the reading of the licence text,
     not legal advice;
   - it runs on its own origin, separate from the Catronaut app, and talks to it only through
     `postMessage`, keeping Catronaut's code a separate program;
   - npm packages still come from CodeSandbox's packager (open question 3); until that is
     replaced, the preview depends on that service for dependencies;
   - the CodeSandbox-hosted bundler remains a fallback, e.g. for local development.
6. **Default animation library: `motion`.** GSAP is technically vetted but not allowed until open
   question 2 is answered.

## Open questions

These are for the project owner, not for this spike:

1. **Bundler licence — settled 2026-09-26: self-host** (Decision 5). Serving the bundler from our
   own domain distributes GPLv3 code to users' browsers, hence the obligations listed there. A
   legal review before production is still advisable.
2. **GSAP.** Is an AI website builder a "tool that allows users to build visual animations without
   code"? If yes, GSAP needs written consent from GSAP/Webflow or has to be dropped.
3. **npm packager.** Fully independent hosting would also need an npm packager/registry proxy
   (`customNpmRegistries`) — not tested here.

## Consequences

- The agent can write idiomatic App Router code, including `async` pages with `await params`,
  and the same files export to a real Next.js build (checked later by M6.5).
- The preview is **more permissive than Next.js** in three places (Node APIs, `"use server"`,
  nested async components). Without M0.5 the agent would ship code that previews fine and fails
  `next build`.
- Large libraries are slow on first use: three.js adds ≈ 5–6 s after the first render, mostly
  transpiling in the browser.
- drei presets that fetch assets from GitHub CDNs work but add third-party hosts; the contract
  steers the agent to plain lights.
- A preview crash in a lazy chunk surfaces seconds after the page looks fine; M2.7's
  `check_preview` timeout must account for it.

## Pitfalls met while measuring

- `three.cjs` calls `process.emitWarning`, missing from the bundler's `process` polyfill (fixed
  in the bridge).
- The first driver read the error list right after the first render and missed the lazy-chunk
  crash; it now re-reads errors after the checks and waits for a fixture-specific element.
- React logs every caught `notFound()` as `console.error`; the runtime's `onCaughtError` now
  ignores `NEXT_NOT_FOUND` / `NEXT_REDIRECT`.
- Sandpack sizes its iframe inline; the host page needs `width/height: 100% !important`.
- The bundler reports "[BABEL] … deoptimised the styling … exceeds the max of 500KB" as a console
  error for big packages (three); it is noise.

## How to re-run

```bash
cd evals/spikes/m0_3/harness && npm ci && npm run build && cd ../../../..
uv run playwright install chromium
uv run python -m evals.spikes.m0_3.run_fixtures                 # hosted bundler
# self-hosted bundler (see evals/spikes/m0_3/README.md for the download):
uv run python -m evals.spikes.m0_3.run_fixtures --bundler-dir evals/spikes/m0_3/vendor/bundler
```

Results land in `m0_3_results/<hosted|self>/` (`results.json` plus two PNGs per rendering fixture).
