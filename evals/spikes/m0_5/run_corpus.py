"""M0.5 — run the static verifier and a tsc baseline over the starter and the seeded-error corpus.

Install the tsc baseline once (packages only; --ignore-scripts, nothing is ever run but tsc):
    cd evals/spikes/m0_5/tsc && npm ci --ignore-scripts && cd ../../../..
Then:
    uv run python -m evals.spikes.m0_5.run_corpus                 # verifier + tsc
    uv run python -m evals.spikes.m0_5.run_corpus --no-tsc        # verifier only
    uv run python -m evals.spikes.m0_5.run_corpus --only static/middleware errors/syntax

Cases: the M0.3 fixtures (starter, deps/*, errors/*) and evals/spikes/m0_5/corpus/<layer>/*. Each
case names the layer expected to catch it: `static` (this verifier), `typecheck` (tsc only),
`build` (only `next build` / SSR), `runtime` (only the preview), or `clean` (nothing wrong).
Results go to m0_5_results/results.json and a Markdown summary to stdout.
"""

import argparse
import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evals.spikes.m0_5.verifier import verify

HERE = Path(__file__).parent
M0_3_FIXTURES = HERE.parent / "m0_3" / "fixtures"
CORPUS = HERE / "corpus"
TSC_DIR = HERE / "tsc"
TSC_WORK = TSC_DIR / "work"  # under TSC_DIR so module resolution finds tsc/node_modules
RESULTS = Path("m0_5_results")
TSC_ERROR = re.compile(
    r"^(?P<path>[^(]+)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.*)$"
)

# M0.3 fixtures predate the layer labels; the preview results they encode are in ADR-0002
M0_3_EXPECT: dict[str, tuple[str, list[str]]] = {
    "starter": ("clean", []),
    "deps/motion": ("clean", []),
    "deps/ui-utils": ("clean", []),
    "deps/gsap-lenis": ("static", ["package.on-hold"]),
    "deps/three-r3f": ("static", ["three.environment-preset"]),
    "errors/async-component": ("static", ["component.nested-async"]),
    "errors/async-page": ("clean", []),
    "errors/font-local": ("static", ["module.forbidden"]),
    "errors/missing-import": ("static", ["import.unresolved"]),
    "errors/next-headers": ("static", ["module.forbidden"]),
    "errors/node-api": ("static", ["module.forbidden"]),
    "errors/render-throw": ("runtime", []),
    "errors/route-handler": ("static", ["file.forbidden-route"]),
    "errors/server-only": ("static", ["module.forbidden", "package.not-vetted"]),
    "errors/syntax": ("static", ["parse.syntax"]),
    "errors/undeclared-package": ("static", ["package.undeclared"]),
    "errors/unhandled-rejection": ("runtime", []),
    "errors/use-server": ("static", ["directive.use-server"]),
}

TSCONFIG_CHECK = {
    "extends": "./tsconfig.json",
    # what create-next-app adds on top of the starter's tsconfig
    "compilerOptions": {
        "noEmit": True,
        "skipLibCheck": True,
        "isolatedModules": True,
        "esModuleInterop": True,
        "allowJs": True,
        "resolveJsonModule": True,
        "incremental": False,
    },
    "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
    "exclude": ["node_modules"],
}
NEXT_ENV = '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n'


@dataclass
class Case:
    name: str
    layer: str
    rules: list[str]
    note: str = ""
    files: dict[str, bytes] = field(default_factory=dict[str, bytes], repr=False)


@dataclass
class Result:
    name: str
    layer: str
    expected: list[str]
    note: str
    found: list[str]  # rendered findings
    rules: list[str]  # distinct rules found
    static_ms: float
    static_caught: bool
    static_extra: list[str]  # rules found that the case did not expect
    tsc_errors: list[str] | None = None
    tsc_ms: float | None = None


def read_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "fixture.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def overlay(directory: Path, manifest: dict[str, Any]) -> dict[str, bytes]:
    """Files of a fixture: its base (recursively, from the M0.3 fixtures) plus its own files."""
    files: dict[str, bytes] = {}
    if "base" in manifest:
        base_dir = M0_3_FIXTURES / manifest["base"]
        files.update(overlay(base_dir, read_manifest(base_dir)))
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "fixture.json":
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    if manifest.get("dependencies"):
        package = json.loads(files["package.json"])
        package["dependencies"] = {**package.get("dependencies", {}), **manifest["dependencies"]}
        files["package.json"] = (json.dumps(package, indent=2) + "\n").encode()
    return files


def load_cases() -> list[Case]:
    cases: list[Case] = []
    for name, (layer, rules) in M0_3_EXPECT.items():
        directory = M0_3_FIXTURES / name
        cases.append(Case(name, layer, rules, files=overlay(directory, read_manifest(directory))))
    for manifest_path in sorted(CORPUS.rglob("fixture.json")):
        manifest = json.loads(manifest_path.read_text("utf-8"))
        expect = manifest["expect"]
        name = manifest_path.parent.relative_to(CORPUS).as_posix()
        files = overlay(manifest_path.parent, manifest)
        cases.append(Case(name, expect["layer"], expect["rules"], expect.get("note", ""), files))
    return cases


def run_static(case: Case) -> Result:
    started = time.perf_counter()
    findings = verify(case.files)
    elapsed = (time.perf_counter() - started) * 1000
    rules = sorted({f.rule for f in findings})
    return Result(
        name=case.name,
        layer=case.layer,
        expected=case.rules,
        note=case.note,
        found=[str(f) for f in findings],
        rules=rules,
        static_ms=round(elapsed, 1),
        static_caught=bool(findings) and (not case.rules or bool(set(case.rules) & set(rules))),
        static_extra=[r for r in rules if r not in case.rules],
    )


def run_tsc(case: Case) -> tuple[list[str], float]:
    work = TSC_WORK / case.name.replace("/", "__")
    shutil.rmtree(work, ignore_errors=True)
    for path, content in case.files.items():
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (work / "tsconfig.check.json").write_text(json.dumps(TSCONFIG_CHECK, indent=2), "utf-8")
    if not (work / "next-env.d.ts").exists():
        (work / "next-env.d.ts").write_text(NEXT_ENV, "utf-8")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is not on PATH")
    tsc = TSC_DIR / "node_modules" / "typescript" / "bin" / "tsc"
    started = time.perf_counter()
    completed = subprocess.run(
        [node, str(tsc), "-p", "tsconfig.check.json", "--pretty", "false"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=300,
    )
    elapsed = (time.perf_counter() - started) * 1000
    errors: list[str] = []
    for line in completed.stdout.splitlines():
        match = TSC_ERROR.match(line.strip())
        if match:
            errors.append(f"{match['path']}:{match['line']}: {match['code']} {match['msg'][:120]}")
    if completed.returncode != 0 and not errors:
        errors.append(f"tsc exited {completed.returncode}: {completed.stdout[:200]}")
    return errors, round(elapsed, 1)


def summarise(results: list[Result], with_tsc: bool) -> str:
    out: list[str] = []
    header = "| Case | Layer | Static | Extra rules |" + (" tsc |" if with_tsc else "")
    out += [header, "|---" * (header.count("|") - 1) + "|"]
    for r in results:
        if r.layer == "clean":
            static = "clean" if not r.rules else "FALSE POSITIVE"
        else:
            static = "caught" if r.static_caught else "missed"
        row = f"| `{r.name}` | {r.layer} | {static} | {', '.join(r.static_extra) or ''} |"
        if with_tsc:
            tsc = "-" if not r.tsc_errors else f"{len(r.tsc_errors)} error(s)"
            row += f" {tsc} |"
        out.append(row)

    out += ["", "| Layer | Cases | Static caught | tsc caught | Static only | tsc only | Neither |"]
    out.append("|---|---|---|---|---|---|---|")
    for layer in ("static", "typecheck", "build", "runtime"):
        group = [r for r in results if r.layer == layer]
        if not group:
            continue
        s = {r.name for r in group if r.static_caught}
        t = {r.name for r in group if r.tsc_errors} if with_tsc else set[str]()
        names = {r.name for r in group}
        tsc_cell = str(len(t)) if with_tsc else "n/a"
        out.append(
            f"| {layer} | {len(group)} | {len(s)} | {tsc_cell} | {len(s - t)} | "
            f"{len(t - s) if with_tsc else 'n/a'} | {len(names - s - t)} |"
        )

    clean = [r for r in results if r.layer == "clean"]
    tsc_fp = str(sum(bool(r.tsc_errors) for r in clean)) if with_tsc else "n/a"
    out += ["", f"False positives on {len(clean)} clean projects: static "
            f"{sum(bool(r.rules) for r in clean)}, tsc {tsc_fp}."]  # fmt: skip

    static_ms = sorted(r.static_ms for r in results)
    out += ["", f"Static verifier per project: median {static_ms[len(static_ms) // 2]} ms, "
            f"max {static_ms[-1]} ms."]  # fmt: skip
    if with_tsc:
        tsc_ms = sorted(r.tsc_ms or 0 for r in results)
        out.append(f"tsc per project: median {tsc_ms[len(tsc_ms) // 2]} ms, max {tsc_ms[-1]} ms.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="case names to run")
    parser.add_argument("--no-tsc", action="store_true", help="skip the tsc baseline")
    parser.add_argument("--workers", type=int, default=4, help="parallel tsc processes")
    args = parser.parse_args()

    cases = load_cases()
    if args.only:
        cases = [c for c in cases if c.name in args.only]
    results = [run_static(c) for c in cases]
    with_tsc = not args.no_tsc
    if with_tsc:
        if not (TSC_DIR / "node_modules" / "typescript").exists():
            raise SystemExit("tsc baseline not installed; see the module docstring")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for result, (errors, elapsed) in zip(results, pool.map(run_tsc, cases), strict=True):
                result.tsc_errors, result.tsc_ms = errors, elapsed

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False), "utf-8"
    )
    summary = summarise(results, with_tsc)
    (RESULTS / "summary.md").write_text(summary + "\n", "utf-8")
    print(summary)


if __name__ == "__main__":
    main()
