"""Per-run write quotas (M1.4): project-service's limits, checked on the working copy.

A write that project-service would reject is refused when the model makes it, with a hint, instead
of failing the whole batch with `413` at the next flush.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.workspace.errors import WorkspaceError


@dataclass(frozen=True)
class WriteQuota:
    # Limits of project-service's files API (ref/ai-service-integration.md §4.3)
    max_file_bytes: int = 512 * 1024
    max_files: int = 1000
    max_total_bytes: int = 10 * 1024 * 1024
    # Changes per `POST files/changes`; used by the flush, not by the checks below
    max_batch_changes: int = 200
    # Writes and deletes per run. A placeholder until Phase 2 measures real runs
    max_writes_per_run: int = 300
    # Text files only (preview contract). No `.env`: the agent never writes secrets
    allowed_extensions: frozenset[str] = frozenset(
        {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            ".json",
            ".css",
            ".html",
            ".md",
            ".mdx",
            ".txt",
            ".svg",
        }
    )


def check_content(path: str, content: str, quota: WriteQuota) -> int:
    """Check one file's name and content; return its size in UTF-8 bytes."""
    extension = PurePosixPath(path).suffix
    if extension not in quota.allowed_extensions:
        allowed = ", ".join(sorted(quota.allowed_extensions))
        raise WorkspaceError(
            f"files like {path!r} cannot be written; only text source files are allowed.",
            f"Use one of these extensions: {allowed}.",
        )
    if "\x00" in content:
        raise WorkspaceError(
            f"the content for {path!r} contains a NUL character.",
            "Write plain text only; remove the NUL character.",
        )
    try:
        size = len(content.encode("utf-8"))
    except UnicodeEncodeError:
        raise WorkspaceError(
            f"the content for {path!r} is not valid UTF-8 text.",
            "Write plain text only; remove the invalid characters.",
        ) from None
    if size > quota.max_file_bytes:
        raise WorkspaceError(
            f"{path!r} would be {size} bytes; the limit is {quota.max_file_bytes} per file.",
            "Split the file into smaller modules.",
        )
    return size


def check_tree(sizes: Mapping[str, int], path: str, size: int, quota: WriteQuota) -> None:
    """Check the project after writing `size` bytes to `path`; `sizes` is the tree before it."""
    files = len(sizes) + (0 if path in sizes else 1)
    if files > quota.max_files:
        raise WorkspaceError(
            f"writing {path!r} would make {files} files; the limit is {quota.max_files}.",
            "Reuse or delete existing files instead of adding new ones.",
        )
    total = sum(sizes.values()) - sizes.get(path, 0) + size
    if total > quota.max_total_bytes:
        raise WorkspaceError(
            f"writing {path!r} would make the project {total} bytes; "
            f"the limit is {quota.max_total_bytes}.",
            "Make files smaller or delete files that are no longer needed.",
        )
    # A path cannot be both a file and a directory (`app` vs `app/page.tsx`)
    if any(existing.startswith(path + "/") for existing in sizes):
        raise WorkspaceError(
            f"{path!r} is already a directory.",
            "Choose a file name that is not an existing directory.",
        )
    parts = path.split("/")
    for end in range(1, len(parts)):
        parent = "/".join(parts[:end])
        if parent in sizes:
            raise WorkspaceError(
                f"{parent!r} is a file, so {path!r} cannot be created inside it.",
                "Choose a path whose directories are not existing files.",
            )


def check_write_count(writes: int, quota: WriteQuota) -> None:
    """Check that the run may make one more write or delete after `writes` of them."""
    if writes >= quota.max_writes_per_run:
        raise WorkspaceError(
            f"this run has already made {writes} file changes; "
            f"the limit is {quota.max_writes_per_run}.",
            "Finish the task with the changes made so far and report what is left.",
        )
