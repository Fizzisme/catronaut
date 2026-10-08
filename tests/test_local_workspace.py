import asyncio
from pathlib import Path

import pytest

from app.core.workspace.base import FlushResult
from app.core.workspace.errors import WorkspaceConflict
from app.core.workspace.local import LocalWorkspace


def write_tree(root: Path, files: dict[str, bytes]) -> None:
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def read_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_open_loads_text_files_exactly_and_skips_the_rest(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "app/page.tsx": b"line 1\r\nline 2\n",
            "app/[slug]/page.tsx": "ệ".encode(),
            "public/logo.png": b"\x89PNG\x00\xff",
            "node_modules/react/index.js": b"x",
            ".git/HEAD": b"ref",
        },
    )

    async def run() -> None:
        async with LocalWorkspace(tmp_path) as workspace:
            assert workspace.base_revision == 0
            assert workspace.list_paths() == ["app/[slug]/page.tsx", "app/page.tsx"]
            assert workspace.read("app/page.tsx") == "line 1\r\nline 2\n"
            assert workspace.read("app/[slug]/page.tsx") == "ệ"

    asyncio.run(run())


def test_flush_writes_the_batch_and_grows_the_revision(tmp_path: Path) -> None:
    write_tree(tmp_path, {"old.ts": b"old", "keep.ts": b"keep"})

    async def run() -> list[FlushResult | None]:
        async with LocalWorkspace(tmp_path) as workspace:
            workspace.write("app/page.tsx", "a\nb\n")
            workspace.delete("old.ts")
            first = await workspace.flush("step 1")
            workspace.write("keep.ts", "kept")
            second = await workspace.flush("step 2")
            nothing = await workspace.flush("step 3")
            return [first, second, nothing]

    assert asyncio.run(run()) == [
        FlushResult(1, ("app/page.tsx", "old.ts")),
        FlushResult(2, ("keep.ts",)),
        None,
    ]
    # "\n" stays "\n" on Windows, and no staging files are left behind
    assert read_tree(tmp_path) == {"app/page.tsx": b"a\nb\n", "keep.ts": b"kept"}


def test_the_next_run_starts_from_the_last_revision(tmp_path: Path) -> None:
    async def run() -> int:
        async with LocalWorkspace(tmp_path) as workspace:
            workspace.write("a.ts", "a")
        async with LocalWorkspace(tmp_path) as workspace:
            return workspace.base_revision

    # The first run's close stored its write as revision 1
    assert asyncio.run(run()) == 1


def test_close_flushes_what_is_left(tmp_path: Path) -> None:
    async def run() -> None:
        async with LocalWorkspace(tmp_path) as workspace:
            workspace.write("a.ts", "a")

    asyncio.run(run())

    assert read_tree(tmp_path) == {"a.ts": b"a"}


def test_a_leased_project_cannot_be_opened_again(tmp_path: Path) -> None:
    async def run() -> None:
        async with LocalWorkspace(tmp_path):
            with pytest.raises(WorkspaceConflict, match="leased"):
                await LocalWorkspace(tmp_path).open()
        # Released on close, so the next run can take it
        async with LocalWorkspace(tmp_path):
            pass

    asyncio.run(run())


def test_the_lease_is_released_when_the_run_fails(tmp_path: Path) -> None:
    async def run() -> None:
        with pytest.raises(ValueError):
            async with LocalWorkspace(tmp_path):
                raise ValueError("the run failed")
        async with LocalWorkspace(tmp_path):
            pass

    asyncio.run(run())


def test_a_file_can_replace_a_directory_in_one_batch(tmp_path: Path) -> None:
    write_tree(tmp_path, {"lib.ts/index.ts": b"dir"})

    async def run() -> None:
        async with LocalWorkspace(tmp_path) as workspace:
            workspace.delete("lib.ts/index.ts")
            workspace.write("lib.ts", "file")

    asyncio.run(run())

    assert read_tree(tmp_path) == {"lib.ts": b"file"}


def test_a_directory_can_replace_a_file_in_one_batch(tmp_path: Path) -> None:
    write_tree(tmp_path, {"lib.ts": b"file"})

    async def run() -> None:
        async with LocalWorkspace(tmp_path) as workspace:
            workspace.delete("lib.ts")
            workspace.write("lib.ts/index.ts", "dir")

    asyncio.run(run())

    assert read_tree(tmp_path) == {"lib.ts/index.ts": b"dir"}
