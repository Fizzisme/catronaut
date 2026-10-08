"""Path guard (M1.4): the same path rules as project-service, checked before any file access.

A bad path is an error the model can fix, never silently rewritten (M1.5: arguments are never
transformed), so the model always knows which file it actually touched.
"""

from app.core.workspace.errors import WorkspaceError

MAX_PATH_LENGTH = 300
_FORBIDDEN_CHARS = ("\\", ":", "\x00")
_FORBIDDEN_SEGMENTS = ("", ".", "..")
_HINT = "Use a relative path with '/' separators, e.g. 'app/page.tsx'."


def check_path(raw: str) -> str:
    """Return `raw` unchanged if project-service accepts it, otherwise raise `WorkspaceError`."""
    if not raw:
        raise WorkspaceError("the path is empty.", _HINT)
    if len(raw) > MAX_PATH_LENGTH:
        raise WorkspaceError(
            f"the path is {len(raw)} characters long; the limit is {MAX_PATH_LENGTH}.", _HINT
        )
    for char in _FORBIDDEN_CHARS:
        if char in raw:
            raise WorkspaceError(f"the path {raw!r} contains the character {char!r}.", _HINT)
    if raw.startswith("/"):
        raise WorkspaceError(f"the path {raw!r} is absolute; it must not start with '/'.", _HINT)
    for segment in raw.split("/"):
        if segment in _FORBIDDEN_SEGMENTS:
            raise WorkspaceError(
                f"the path {raw!r} has an empty, '.' or '..' segment.",
                _HINT,
            )
    return raw
