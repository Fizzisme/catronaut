# M0.3 — preview spike

Runs Next.js App Router fixtures in the Sandpack classic bundler with Next.js shims and records
what happens. Findings and decisions: [ADR-0002](../../../docs/adr/0002-preview-runtime.md); the
resulting rules: [preview contract](../../../docs/preview-contract.md).

| Path | What |
|---|---|
| `harness/src/main.ts` | Host page: loads a fixture, starts Sandpack, exposes `window.__preview` |
| `harness/src/translate.ts` | Next.js project → Sandpack files (route table, shims, Tailwind) |
| `harness/src/shims/` | Fake `node_modules/next/**` and `server-only`, plus the App Router runtime |
| `harness/src/sandbox/bridge.js` | Runs inside the iframe: error reports, render events, screenshots |
| `fixtures/` | `starter`, `errors/*`, `deps/*`; `fixture.json` overlays a base fixture and states the expectation |
| `run_fixtures.py` | Playwright driver → `m0_3_results/<hosted\|self>/` |

## Run

```bash
cd evals/spikes/m0_3/harness && npm ci && npm run build && cd ../../../..
uv run playwright install chromium        # once
uv run python -m evals.spikes.m0_3.run_fixtures
uv run python -m evals.spikes.m0_3.run_fixtures --only starter deps/motion
```

To look at one fixture by hand: `npm run dev` in `harness/`, then open
`http://localhost:5173/?fixture=starter` (add `&bundler=<url>` for another bundler).

## Self-hosted bundler

Catronaut self-hosts this bundler (ADR-0002, Decision 5). The build is GPLv3 and 99 MB, so it is
downloaded, never committed:

```bash
mkdir -p evals/spikes/m0_3/vendor/bundler
curl -L -o evals/spikes/m0_3/vendor/bundler.zip \
  https://github.com/LibreChat-AI/codesandbox-client/releases/download/bundler-v12/bundler.zip
# sha256 e6ce913b9066a46b9255e9cd517e6413134523eb2da861bd356e4e1999a654c6
unzip -q evals/spikes/m0_3/vendor/bundler.zip -d evals/spikes/m0_3/vendor/bundler
uv run python -m evals.spikes.m0_3.run_fixtures --bundler-dir evals/spikes/m0_3/vendor/bundler
```
