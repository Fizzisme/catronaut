"""Holds a domain's tool definitions: produces the JSON-schema list handed to
the model and resolves a tool-call name back to a callable `Tool` instance.

The schema shape here is backend-agnostic on purpose — both the native path
(Ollama's `tools` param) and the prompt-based fallback (M2.2, for the 4B) read
name/description/parameters off the same list. Parsing a model's tool-call
output and validating it against `args_schema` is M2.2; timeouts, result
truncation, and allowlisting are M2.3 — this class only holds definitions.
"""

from typing import Iterable, Iterator

from app.core.tools.base import Tool


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool]):
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"duplicate tool name: {tool.name!r}")
            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schema(self) -> list[dict]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.model_json_schema(),
            }
            for tool in self._tools.values()
        ]

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())
