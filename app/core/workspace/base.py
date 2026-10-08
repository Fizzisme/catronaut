"""Workspace (M1.4): the project's files as an in-memory working copy for one run.

ADR-0003 Decision 5: tools read and write the working copy, each write is reported at once as a
`file_changed` event, and the changes reach storage in one atomic batch per safe point (`flush`).
Subclasses only say where the tree comes from and where a batch goes.
"""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Self

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.paths import check_path
from app.core.workspace.quota import WriteQuota, check_content, check_tree, check_write_count

FileOp = Literal["create", "update", "delete"]


@dataclass(frozen=True)
class FileChange:
    """One change to a file; the `file_changed` payload of the run API contract."""

    path: str
    op: FileOp
    # Present unless `op` is `delete`
    content: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class FlushResult:
    """A batch stored as `revision`; the `files_persisted` payload of the run API contract."""

    revision: int
    paths: tuple[str, ...]


def sha256_of(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Workspace(ABC):
    def __init__(self, quota: WriteQuota | None = None) -> None:
        self._quota = quota or WriteQuota()
        self._files: dict[str, str] = {}
        self._sizes: dict[str, int] = {}
        # The tree as storage has it: at open, then after each flush
        self._saved: dict[str, str] = {}
        # Paths touched since the last flush; `pending` compares them with `_saved`
        self._dirty: set[str] = set()
        self._writes = 0
        self._base_revision: int | None = None

    @property
    def base_revision(self) -> int:
        """The revision the run started from: its restore point."""
        if self._base_revision is None:
            raise RuntimeError("the workspace is not open")
        return self._base_revision

    def read(self, path: str) -> str:
        self._require_open()
        content = self._files.get(check_path(path))
        if content is None:
            raise WorkspaceError(f"there is no file {path!r}.", _MISSING_HINT)
        return content

    def exists(self, path: str) -> bool:
        self._require_open()
        return check_path(path) in self._files

    def list_paths(self) -> list[str]:
        self._require_open()
        return sorted(self._files)

    def write(self, path: str, content: str) -> FileChange:
        """Create or replace a file; every check runs before anything changes."""
        self._require_open()
        check_path(path)
        check_write_count(self._writes, self._quota)
        size = check_content(path, content, self._quota)
        check_tree(self._sizes, path, size, self._quota)

        op: FileOp = "update" if path in self._files else "create"
        self._files[path] = content
        self._sizes[path] = size
        self._dirty.add(path)
        self._writes += 1
        return FileChange(path, op, content, sha256_of(content))

    def delete(self, path: str) -> FileChange:
        self._require_open()
        check_path(path)
        if path not in self._files:
            raise WorkspaceError(f"there is no file {path!r} to delete.", _MISSING_HINT)
        check_write_count(self._writes, self._quota)

        del self._files[path]
        del self._sizes[path]
        self._dirty.add(path)
        self._writes += 1
        return FileChange(path, "delete")

    def pending(self) -> tuple[FileChange, ...]:
        """The changes the next flush stores, one per path, compared with what storage has.

        A file created and deleted again, or written back unchanged, has nothing to store.
        """
        changes: list[FileChange] = []
        for path in sorted(self._dirty):
            content = self._files.get(path)
            saved = self._saved.get(path)
            if content == saved:
                continue
            if content is None:
                changes.append(FileChange(path, "delete"))
            else:
                op: FileOp = "create" if saved is None else "update"
                changes.append(FileChange(path, op, content, sha256_of(content)))
        return tuple(changes)

    @abstractmethod
    async def open(self) -> None:
        """Take the lease and load the tree with `_load`."""

    @abstractmethod
    async def flush(self, label: str) -> FlushResult | None:
        """Store `pending()` as one atomic batch, then call `_mark_flushed`.

        Returns None when there is nothing to store. Raises `WorkspaceConflict` when the run
        must stop.
        """

    @abstractmethod
    async def close(self) -> None:
        """Store what is left and release the lease, even if storing fails."""

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _load(self, files: Mapping[str, str], revision: int) -> None:
        """Start the working copy from storage's tree at `revision`."""
        self._files = dict(files)
        self._sizes = {path: len(content.encode("utf-8")) for path, content in files.items()}
        self._saved = dict(files)
        self._dirty.clear()
        self._writes = 0
        self._base_revision = revision

    def _mark_flushed(self) -> None:
        """Storage now has the working copy."""
        self._saved = dict(self._files)
        self._dirty.clear()

    def _require_open(self) -> None:
        if self._base_revision is None:
            raise RuntimeError("the workspace is not open")


_MISSING_HINT = "Check the path; list the project's files to find the right one."
