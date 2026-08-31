"""Tool abstraction domain tools implement to be callable by an agent loop.

Kept intentionally thin at this milestone (M2.1): definition + registry only.
Parsing a model's raw tool-call output against `args_schema` — native vs.
prompt-based extraction, validation, one bounded repair turn — is M2.2, not
here. Execution policy (timeouts, result truncation, allowlisting) is M2.3.
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

    @abstractmethod
    async def run(self, args: BaseModel) -> Any:
        """Execute the tool with validated arguments and return a result."""
