"""Per-domain execution policy for tools (ROADMAP M2.3): which tools a domain may call.

Deliberately narrow — a name allowlist, nothing else. Capability declaration
(fs_read / fs_write / network / subprocess) and enforcement at a single `pre_tool_call`
seam is ROADMAP M8.2, which is explicitly deferred until the loop (Phase 5) is stable —
designing that now would mean guessing at an enforcement point with no loop to hang it on.
"""

from dataclasses import dataclass

from app.core.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolPolicy:
    allowed_tools: frozenset[str]

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools

    @classmethod
    def allow_all(cls, registry: ToolRegistry) -> "ToolPolicy":
        """Every tool in `registry` is allowed. For domains/tests with no restriction —
        not a default a domain should reach for once it has side-effecting tools."""
        return cls(allowed_tools=frozenset(tool.name for tool in registry))
