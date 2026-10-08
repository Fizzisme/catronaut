"""The two ways a workspace operation fails (M1.4)."""

from app.core.tools import ToolError


class WorkspaceError(ToolError):
    """A failure the model caused and can fix: a bad path, a missing file, a quota."""


class WorkspaceConflict(Exception):
    """The run cannot go on safely: the lease was lost, someone else changed the files, or the
    storage refused or failed a request.

    Not a tool observation: the run ends as `failed` with this reason (ADR-0003 Decision 8).
    """
