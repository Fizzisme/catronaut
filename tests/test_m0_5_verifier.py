from pathlib import Path

from evals.spikes.m0_5.run_corpus import load_cases, run_static
from evals.spikes.m0_5.verifier import load_project, verify

STARTER = Path(__file__).parent.parent / "evals" / "spikes" / "m0_3" / "fixtures" / "starter"


def with_files(files: dict[str, str]) -> dict[str, bytes]:
    project = load_project(STARTER)
    project.update({path: text.encode() for path, text in files.items()})
    return project


def rules(project: dict[str, bytes]) -> set[str]:
    return {finding.rule for finding in verify(project)}


def test_starter_is_clean() -> None:
    assert verify(load_project(STARTER)) == []


def test_client_boundary_follows_imports_until_use_client() -> None:
    hook = 'import { useState } from "react";\nexport function Hook() { useState(0); return null; }'
    page = 'import { Hook } from "@/components/hook";\nexport default () => <Hook />;'
    reached = with_files({"components/hook.tsx": hook, "app/about/page.tsx": page})
    assert "client.boundary" in rules(reached)
    marked = with_files(
        {"components/hook.tsx": '"use client";\n' + hook, "app/about/page.tsx": page}
    )
    assert "client.boundary" not in rules(marked)


def test_mismatched_jsx_tags_are_reported() -> None:
    page = "export default function P() { return <h1>x</h2>; }\n"
    assert rules(with_files({"app/about/page.tsx": page})) == {"parse.jsx-mismatch"}


def test_type_only_imports_skip_package_checks() -> None:
    page = 'import type { Mesh } from "three";\nexport default function P() { return null; }\n'
    assert rules(with_files({"app/about/page.tsx": page})) == set()


def test_every_static_corpus_case_is_caught_without_extra_rules() -> None:
    results = [run_static(case) for case in load_cases()]
    for result in results:
        if result.layer == "static":
            assert result.static_caught, result.name
        if result.layer in ("static", "clean"):
            assert result.static_extra == [], result.name
