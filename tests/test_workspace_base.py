import asyncio

import pytest

from app.core.workspace.base import FileChange, FlushResult, Workspace, sha256_of
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.quota import WriteQuota


class MemoryWorkspace(Workspace):
    """The smallest storage: a dict and a revision counter."""

    def __init__(self, files: dict[str, str], quota: WriteQuota | None = None) -> None:
        super().__init__(quota)
        self.stored = dict(files)
        self.revision = 7
        self.batches: list[tuple[FileChange, ...]] = []
        self.closed = False

    async def open(self) -> None:
        self._load(self.stored, self.revision)

    async def flush(self, label: str) -> FlushResult | None:
        changes = self.pending()
        if not changes:
            return None
        for change in changes:
            if change.content is None:
                del self.stored[change.path]
            else:
                self.stored[change.path] = change.content
        self.revision += 1
        self.batches.append(changes)
        self._mark_flushed()
        return FlushResult(self.revision, tuple(change.path for change in changes))

    async def close(self) -> None:
        await self.flush("end")
        self.closed = True


def opened(files: dict[str, str] | None = None, quota: WriteQuota | None = None) -> MemoryWorkspace:
    workspace = MemoryWorkspace(files or {}, quota)
    asyncio.run(workspace.open())
    return workspace


def test_open_loads_the_tree_and_the_base_revision() -> None:
    workspace = opened({"b.ts": "b", "a.ts": "a"})

    assert workspace.base_revision == 7
    assert workspace.list_paths() == ["a.ts", "b.ts"]
    assert workspace.read("a.ts") == "a"
    assert workspace.exists("b.ts")
    assert not workspace.exists("c.ts")
    assert workspace.pending() == ()


def test_use_before_open_is_a_bug() -> None:
    workspace = MemoryWorkspace({})

    with pytest.raises(RuntimeError):
        workspace.read("a.ts")
    with pytest.raises(RuntimeError):
        _ = workspace.base_revision


def test_reading_a_missing_file_is_an_error() -> None:
    with pytest.raises(WorkspaceError, match="no file 'a.ts'"):
        opened().read("a.ts")


def test_paths_are_checked_on_read() -> None:
    with pytest.raises(WorkspaceError, match="segment"):
        opened().read("../secret.ts")


def test_write_reports_create_then_update() -> None:
    workspace = opened()

    assert workspace.write("a.ts", "1") == FileChange("a.ts", "create", "1", sha256_of("1"))
    assert workspace.write("a.ts", "2") == FileChange("a.ts", "update", "2", sha256_of("2"))
    assert workspace.read("a.ts") == "2"


def test_delete_reports_a_delete() -> None:
    workspace = opened({"a.ts": "a"})

    assert workspace.delete("a.ts") == FileChange("a.ts", "delete")
    assert not workspace.exists("a.ts")


def test_deleting_a_missing_file_is_an_error() -> None:
    with pytest.raises(WorkspaceError, match="no file 'a.ts' to delete"):
        opened().delete("a.ts")


def test_a_rejected_write_changes_nothing() -> None:
    workspace = opened({"a.ts": "a"}, WriteQuota(max_file_bytes=3))

    with pytest.raises(WorkspaceError):
        workspace.write("a.ts", "toolong")

    assert workspace.read("a.ts") == "a"
    assert workspace.pending() == ()


def test_deletes_count_towards_the_write_limit() -> None:
    workspace = opened({"a.ts": "a"}, WriteQuota(max_writes_per_run=2))
    workspace.write("b.ts", "b")
    workspace.delete("a.ts")

    with pytest.raises(WorkspaceError, match="2 file changes"):
        workspace.write("c.ts", "c")


def test_pending_has_one_change_per_path_against_storage() -> None:
    workspace = opened({"keep.ts": "k", "edit.ts": "e", "gone.ts": "g", "same.ts": "s"})
    workspace.write("edit.ts", "e1")
    workspace.write("edit.ts", "e2")
    workspace.delete("gone.ts")
    workspace.write("new.ts", "n")
    workspace.write("same.ts", "changed")
    workspace.write("same.ts", "s")
    workspace.write("temp.ts", "t")
    workspace.delete("temp.ts")

    assert workspace.pending() == (
        FileChange("edit.ts", "update", "e2", sha256_of("e2")),
        FileChange("gone.ts", "delete"),
        FileChange("new.ts", "create", "n", sha256_of("n")),
    )


def test_flush_stores_the_batch_and_clears_pending() -> None:
    workspace = opened({"a.ts": "a"})
    workspace.write("b.ts", "b")

    result = asyncio.run(workspace.flush("step 1"))

    assert result == FlushResult(8, ("b.ts",))
    assert workspace.stored == {"a.ts": "a", "b.ts": "b"}
    assert workspace.pending() == ()
    # The restore point stays where the run started
    assert workspace.base_revision == 7


def test_after_a_flush_pending_compares_with_the_new_tree() -> None:
    workspace = opened()
    workspace.write("a.ts", "1")
    asyncio.run(workspace.flush("step 1"))
    workspace.write("a.ts", "2")

    assert workspace.pending() == (FileChange("a.ts", "update", "2", sha256_of("2")),)


def test_async_with_opens_and_closes() -> None:
    workspace = MemoryWorkspace({})

    async def run() -> None:
        async with workspace as ws:
            ws.write("a.ts", "a")

    asyncio.run(run())

    assert workspace.closed
    assert workspace.stored == {"a.ts": "a"}
