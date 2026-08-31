"""Tool abstraction domain tools implement to be callable by an agent loop.

Parsing a model's raw tool-call output against `args_schema` — native vs.
prompt-based extraction, validation, one bounded repair turn — is M2.2.
`run()` always receives an already-validated `args_schema` instance; a `Tool`
subclass never sees raw model output.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    # M2.3 — no default: a tool must say whether it only reads or has side effects.
    # Silently defaulting this would let a side-effecting tool pass as safe by omission.
    read_only: ClassVar[bool]

    # M2.3 — per-tool timeout enforced by ToolExecutor. 30s is a safety net, not a
    # normal-case expectation: every tool in the first pack (M2.4) is fast in-process
    # work (contrast math, an in-memory lookup, string formatting).
    timeout_s: ClassVar[float] = 30.0

    @abstractmethod
    async def run(self, args: BaseModel) -> Any:
        """Execute the tool with validated arguments and return a result."""
