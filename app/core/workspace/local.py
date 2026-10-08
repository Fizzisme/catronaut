"""LocalWorkspace (M1.4): a project directory on disk, for development, tests and evaluation.

ADR-0003 Decision 9: it keeps project-service's semantics so nothing waits for that service —
a revision that grows by one per stored batch, all-or-nothing batches, and one lease per project.
Revisions and leases live in this process only; a restart starts the revision again at 0.
"""

import asyncio
import os
import uuid
from pathlib import Path

from app.core.workspace.base import FileChange, FlushResult, Workspace
from app.core.workspace.errors import WorkspaceConflict
from app.core.workspace.quota import WriteQuota

# Where a flush stages new contents before moving them into place
_STAGING_DIR = ".catronaut-staging"
# Tooling output and our own staging, not project files
_IGNORED_DIRS = frozenset({".git", "node_modules", ".next", _STAGING_DIR})

# Per project root, shared by every LocalWorkspace of this process
_revisions: dict[Path, int] = {}
_leased: set[Path] = set()


class LocalWorkspace(Workspace):
    def __init__(self, root: Path, quota: WriteQuota | None = None) -> None:
        super().__init__(quota)
        self._root = root.resolve()
        self._holds_lease = False

    async def open(self) -> None:
        if self._root in _leased:
            raise WorkspaceConflict(f"the project at {self._root} is leased by another run")
        _leased.add(self._root)
        self._holds_lease = True
        try:
            files = await asyncio.to_thread(self._read_tree)
        except BaseException:
            self._release()
            raise
        self._load(files, _revisions.get(self._root, 0))

    async def flush(self, label: str) -> FlushResult | None:
        if not self._holds_lease:
            raise WorkspaceConflict("the workspace no longer holds the project lease")
        changes = self.pending()
        if not changes:
            return None
        await asyncio.to_thread(self._commit, changes)
        revision = _revisions.get(self._root, 0) + 1
        _revisions[self._root] = revision
        self._mark_flushed()
        return FlushResult(revision, tuple(change.path for change in changes))

    async def close(self) -> None:
        try:
            await self.flush("end")
        finally:
            self._release()

    def _release(self) -> None:
        if self._holds_lease:
            _leased.discard(self._root)
            self._holds_lease = False

    def _read_tree(self) -> dict[str, str]:
        files: dict[str, str] = {}
        for path in self._root.rglob("*"):
            relative = path.relative_to(self._root)
            if not path.is_file() or _IGNORED_DIRS.intersection(relative.parts):
                continue
            try:
                # Bytes, not `read_text`: it would turn "\r\n" into "\n" and change the content
                files[relative.as_posix()] = path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                # Binary files are not project files (preview contract); the agent never sees them
                continue
        return files

    def _commit(self, changes: tuple[FileChange, ...]) -> None:
        """Write every new content to a staging directory first, then move them all into place.

        A failure while staging leaves the project unchanged. Only a crash during the final
        moves can leave part of a batch, which a local directory cannot rule out.
        """
        staging = self._root / _STAGING_DIR
        staging.mkdir(exist_ok=True)
        staged: list[tuple[Path, Path]] = []
        try:
            for change in changes:
                if change.content is None:
                    continue
                temporary = staging / uuid.uuid4().hex
                # newline="": keep "\n" as written; Windows would otherwise write "\r\n"
                temporary.write_text(change.content, encoding="utf-8", newline="")
                staged.append((temporary, self._root / change.path))
        except BaseException:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            staging.rmdir()
            raise

        # Deletes first: a deleted file `app` frees the name for a new directory `app/`
        for change in changes:
            if change.content is None:
                target = self._root / change.path
                target.unlink(missing_ok=True)
                self._remove_empty_parents(target)
        for temporary, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, target)
        staging.rmdir()

    def _remove_empty_parents(self, path: Path) -> None:
        """Remove directories a delete left empty, so the path can later become a file."""
        parent = path.parent
        while parent != self._root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
