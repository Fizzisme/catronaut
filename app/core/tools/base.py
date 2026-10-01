"""Tool framework (M1.3): what a tool is, and how its failures reach the model.

Book guide ch05 §5.1.5: a tool failure is an observation the model can act on, never a crashed
run, so every error says what went wrong and what to do next.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode
from pydantic_core import CoreSchema

_Text = Annotated[str, Field(min_length=1)]


class ToolDescription(BaseModel):
    """The description template every tool fills in (book guide ch04 §4.2.2).

    Every section is required, so a one-line description fails when the tool is defined, not when
    the model later guesses wrong. `render` is deterministic, so the tool list sent each step is
    byte-identical and stays in the KV cache (ROADMAP principle 4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: _Text
    when_to_use: _Text
    when_not_to_use: _Text
    returns: _Text
    cost: _Text
    # Example calls, e.g. `Read(path="app/page.tsx", offset=1, limit=200)`
    examples: Annotated[tuple[_Text, ...], Field(min_length=1, max_length=5)]

    def render(self) -> str:
        examples = "\n".join(f"- {example}" for example in self.examples)
        return (
            f"{self.summary}\n\n"
            f"When to use:\n{self.when_to_use}\n\n"
            f"When not to use:\n{self.when_not_to_use}\n\n"
            f"Returns:\n{self.returns}\n\n"
            f"Cost:\n{self.cost}\n\n"
            f"Examples:\n{examples}"
        )


@dataclass(frozen=True)
class ToolResult:
    # What the model reads as the observation of its call
    content: str
    is_error: bool = False


class Tool(Protocol):
    """What the agent loop needs from a tool."""

    @property
    def name(self) -> str: ...

    @property
    def spec(self) -> dict[str, Any]:
        """The OpenAI function definition sent to the model."""
        ...

    async def run(self, arguments: str) -> ToolResult:
        """Run with the raw JSON arguments the model produced."""
        ...


ErrorKind = Literal["invalid_arguments", "tool_error", "unknown_tool", "internal_error"]


class ToolError(Exception):
    """An expected failure a tool reports, such as a file that does not exist."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


def format_error(kind: ErrorKind, message: str, hint: str) -> str:
    """The one shape every tool error takes in the model's context."""
    return f"Error ({kind}): {message}\nHint: {hint}"


class ToolArgs(BaseModel):
    """Base for a tool's arguments: a misspelt or invented argument is an error, not ignored."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class _NoTitles(GenerateJsonSchema):
    """Leaves out the titles pydantic derives from names ("Path" for `path`): tokens, no meaning."""

    def field_title_should_be_set(self, schema: Any) -> bool:
        return False

    def generate(self, schema: CoreSchema, mode: JsonSchemaMode = "validation") -> dict[str, Any]:
        json_schema = super().generate(schema, mode)
        json_schema.pop("title", None)
        return json_schema


class BaseTool[ArgsT: ToolArgs](ABC):
    """A tool whose arguments are a pydantic model; subclasses fill in the class attributes.

    The spec is built once, so it is byte-identical on every step (ROADMAP principle 4).
    """

    name: ClassVar[str]
    description: ClassVar[ToolDescription]
    args_model: type[ArgsT]

    def __init__(self) -> None:
        self._spec: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description.render(),
                "parameters": self.args_model.model_json_schema(schema_generator=_NoTitles),
            },
        }

    @property
    def spec(self) -> dict[str, Any]:
        return self._spec

    @abstractmethod
    async def execute(self, args: ArgsT) -> ToolResult | str:
        """The tool's work, run with arguments that are already validated."""

    async def run(self, arguments: str) -> ToolResult:
        try:
            args = self.args_model.model_validate_json(arguments, strict=True)
        except ValidationError as exc:
            problems = "\n".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['msg']}"
                for error in exc.errors()
            )
            content = format_error(
                "invalid_arguments",
                problems,
                "Fix these arguments to match the tool's schema and call it again.",
            )
            return ToolResult(content=content, is_error=True)

        try:
            result = await self.execute(args)
        except ToolError as exc:
            content = format_error("tool_error", exc.message, exc.hint)
            return ToolResult(content=content, is_error=True)

        if isinstance(result, str):
            return ToolResult(result)
        return result
