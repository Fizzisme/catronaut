# M0.5 — static-verification spike

Checks a generated Next.js project against the [preview contract](../../../docs/preview-contract.md)
without building or running it (ROADMAP D5), and measures what slips through against a `tsc`
baseline. Findings and decision: [ADR-0004](../../../docs/adr/0004-static-verification.md).

| Path | What |
|---|---|
| `verifier.py` | tree-sitter verifier: parse, import resolution, dependency allowlist, file conventions, server features, Server/Client boundary |
| `corpus/<layer>/<case>/` | Seeded errors; `fixture.json` overlays an M0.3 fixture (`base`) and names the layer expected to catch it |
| `run_corpus.py` | Runs the verifier and `tsc --noEmit` on the M0.3 fixtures and the corpus → `m0_5_results/` |
| `tsc/package.json` | Type-check baseline: the packages a real project would have; installed with `--ignore-scripts` |

Layers: `static` (this verifier must catch it), `typecheck` (only `tsc`), `build` (only
`next build` / SSR), `runtime` (only the preview), `clean` (nothing wrong).

## Run

```bash
uv run python -m evals.spikes.m0_5.verifier evals/spikes/m0_3/fixtures/starter   # one project
cd evals/spikes/m0_5/tsc && npm ci --ignore-scripts && cd ../../../..               # once, ~1 min
uv run python -m evals.spikes.m0_5.run_corpus
uv run python -m evals.spikes.m0_5.run_corpus --no-tsc                              # verifier only
uv run python -m evals.spikes.m0_5.run_corpus --only static/middleware typecheck/prop-type
```

On Windows consoles set `PYTHONIOENCODING=utf-8`. `tsc` runs in `tsc/work/<case>/` so module
resolution finds `tsc/node_modules`; nothing there is executed.
