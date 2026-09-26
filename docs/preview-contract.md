# Preview contract

- **Version:** v1 · 2026-09-26 · from the M0.3 spike ([ADR-0002](adr/0002-preview-runtime.md))
- **Audience:** the agent's prompts and verifiers (M0.5, M2.6) and the frontend team that owns the
  preview runtime.

The agent writes a real **Next.js App Router project, frontend only**. It must run in the browser
preview (Sandpack classic bundler + Next.js shims) **and** build with `next build` unchanged.
Anything outside this contract either fails in the preview or, worse, previews fine and fails the
real build.

Column "Enforced by" says who catches a violation: **preview** = the shim throws a
`[preview contract]` error at runtime; **M0.5** = only the static verifier can catch it, because
the preview silently accepts it.

## Project shape

| Rule | Enforced by |
|---|---|
| App Router under `app/` (or `src/app/`); the root `app/layout.tsx` renders `<html>` and `<body>`. | preview |
| Routes: `page.tsx`, nested `layout.tsx`, `not-found.tsx` at the app root, dynamic segments `[x]`, `[...x]`, `[[...x]]`, route groups `(group)`. | preview |
| Not emulated: `loading.tsx`, `error.tsx`, `global-error.tsx`, `template.tsx`, `default.tsx`, parallel routes (`@slot`), intercepting routes, `middleware.ts`. Do not write them. | M0.5 |
| Every imported npm package is listed in `package.json` `dependencies`, and appears in the [vetted list](#vetted-dependencies). | preview (missing) · M0.5 (not vetted) |
| Path alias `@/*` → project root through `tsconfig.json` `paths` is allowed. | preview |
| Files are text. No binary assets in the project (fonts, images, video); use remote URLs. | M0.5 |

## Allowed

| Feature | Notes |
|---|---|
| `"use client"` | Harmless in the preview; needed for hooks and event handlers in the real build. |
| `export const metadata` with `title` (string or `{ default, template, absolute }`) and `description` | Other metadata fields are ignored by the preview. |
| `next/link` | `href` string or `{ pathname, query, hash }`; `replace`, `scroll`. |
| `next/image` | Remote `src` only; the host must also be listed in `next.config.ts` `images.remotePatterns` for the real build. `fill`, `priority`, `sizes`, `width`/`height`. No static image imports. |
| `next/font/google` | Any family, `weight`, `style`, `variable`, `subsets`, `fallback`. |
| `next/navigation` | `useRouter`, `usePathname`, `useSearchParams`, `useParams`, `notFound`, `redirect`, `permanentRedirect`. `useSelectedLayoutSegment(s)` is approximate (segments from the URL root, not from the calling layout) and untested. |
| `next/dynamic` | `dynamic(() => import(...), { ssr: false, loading })` — use it for WebGL/three scenes. |
| `params` / `searchParams` | As promises (Next.js 15+): read with `use(params)` or `await params` in an `async` page or layout. |
| `async` **page** or **layout** | Supported. It is called once per URL; keep it free of hooks. |
| Tailwind CSS v4 | `app/globals.css` with `@import "tailwindcss";`, `@theme`, `@apply`, imported from the root layout. |

## Forbidden

| Construct | Why | Enforced by |
|---|---|---|
| `"use server"`, Server Actions (`<form action={serverFn}>`) | No server. The preview **silently runs the function in the browser**. | M0.5 |
| `app/**/route.ts` (route handlers), `middleware.ts` | No server; the preview skips them. | M0.5 |
| `next/headers`, `next/server`, `next/cache`, `next/og`, `next/script` | Server-only or third-party script injection. | preview |
| `server-only` | Server-only marker. | preview |
| `next/font/local` | Needs binary font files. Use `next/font/google`. | preview |
| Node built-ins: `fs`, `path`, `os`, `child_process`, `crypto` (Node), `process.env` secrets, … | Frontend only. The preview **silently polyfills `fs`**. | M0.5 |
| Nested `async` components (an `async function` component used inside a page) | Renders in the preview with React warnings and re-runs on every render; only page and layout may be async. | M0.5 |
| `fetch` to our own API routes, `generateStaticParams`, `generateMetadata`, `revalidate`, `dynamic = "force-…"` exports | Server features; ignored or unsupported in the preview. | M0.5 |
| drei `<Environment preset>` and other helpers that download assets from GitHub CDNs | Extra third-party hosts; use plain lights. | M0.5 |

## Vetted dependencies

Tested in the preview on 2026-09-26 (hosted and self-hosted bundler). Versions are the ones
tested; the agent pins them exactly.

| Package | Version | Licence | Status | Notes |
|---|---|---|---|---|
| `react`, `react-dom` | 19.2.0 | MIT | ✅ allowed | |
| `motion` | 13.4.4 | MIT | ✅ allowed — **default animation library** | `motion/react`; `useScroll`, `useTransform` work. |
| `lenis` | 1.3.26 | MIT | ✅ allowed | `lenis/react` `<ReactLenis root>`. |
| `three` | 0.186.1 | MIT | ✅ allowed | Needs the runtime's `process.emitWarning` polyfill. Load through `next/dynamic`; adds ≈ 5–6 s on first load. |
| `@react-three/fiber` | 9.8.1 | MIT | ✅ allowed | Set `gl={{ preserveDrawingBuffer: true }}` so screenshots capture the canvas. |
| `@react-three/drei` | 10.7.9 | MIT | ✅ allowed | Avoid `<Environment preset>` (see Forbidden). |
| `lucide-react` | 1.48.0 | ISC | ✅ allowed | |
| `clsx` | 2.1.1 | MIT | ✅ allowed | |
| `tailwind-merge` | 3.7.0 | MIT | ✅ allowed | |
| `gsap` (+ ScrollTrigger) | 3.15.0 | GSAP Standard License | ⏸ **on hold** | Works technically. Licence question open ([ADR-0002](adr/0002-preview-runtime.md#open-questions)). |
| `@gsap/react` | 2.1.2 | GSAP Standard License | ⏸ **on hold** | Same as `gsap`. |

Provided by the preview, never listed by the agent: `next` (shimmed), `modern-screenshot` (added
by the runtime). Build-time packages (`tailwindcss`, `@tailwindcss/postcss`, `typescript`,
`@types/*`) belong in `devDependencies`; the preview ignores them.

Adding a package: write a fixture in `evals/spikes/m0_3/fixtures/deps/`, run it on both bundlers,
check its licence, then add a row here.

## Error reports the preview produces

For the frontend → `ai-service` preview report (M0.4) and the self-fix loop (M2.7):

| Source | Shape | Example |
|---|---|---|
| Bundler (`show-error`) | `{ title, message, path, line, column }` | `ModuleNotFoundError`, `DependencyNotFoundError`, Babel syntax errors |
| Runtime (bridge) | `{ kind, message, stack, componentStack? }` with `kind` ∈ `window.error`, `unhandledrejection`, `react.render`, `react.uncaught` | `boom during render` |
| Contract shim | message starts with `[preview contract]` | `'next/headers' is not available in the preview` |

Errors from lazily loaded chunks (`next/dynamic`) can arrive several seconds after the first
render; a report is final only after that window.
