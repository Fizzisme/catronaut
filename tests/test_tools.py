import asyncio
import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.tools import BaseTool, ToolArgs, ToolDescription, ToolError, ToolResult

DESCRIPTION: dict[str, Any] = {
    "summary": "Read a text file from the project.",
    "when_to_use": "Before editing a file, or to check what a file contains.",
    "when_not_to_use": "To find files by name; use Glob.",
    "returns": "The file's lines, numbered from 1.",
    "cost": "Cheap; a long file is cut, so read it in parts.",
    "examples": ('Read(path="app/page.tsx")', 'Read(path="app/page.tsx", offset=200, limit=100)'),
}


def test_description_renders_every_section_in_a_fixed_order() -> None:
    text = ToolDescription.model_validate(DESCRIPTION).render()

    assert text == (
        "Read a text file from the project.\n\n"
        "When to use:\nBefore editing a file, or to check what a file contains.\n\n"
        "When not to use:\nTo find files by name; use Glob.\n\n"
        "Returns:\nThe file's lines, numbered from 1.\n\n"
        "Cost:\nCheap; a long file is cut, so read it in parts.\n\n"
        "Examples:\n"
        '- Read(path="app/page.tsx")\n'
        '- Read(path="app/page.tsx", offset=200, limit=100)'
    )


@pytest.mark.parametrize(
    "field", ["summary", "when_to_use", "when_not_to_use", "returns", "cost", "examples"]
)
def test_description_without_a_section_is_rejected(field: str) -> None:
    fields = {name: value for name, value in DESCRIPTION.items() if name != field}
    with pytest.raises(ValidationError):
        ToolDescription.model_validate(fields)


def test_description_with_an_empty_section_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolDescription.model_validate({**DESCRIPTION, "when_not_to_use": ""})


@pytest.mark.parametrize("count", [0, 6])
def test_description_needs_one_to_five_examples(count: int) -> None:
    examples = tuple(f"Read(path='{n}.tsx')" for n in range(count))
    with pytest.raises(ValidationError):
        ToolDescription.model_validate({**DESCRIPTION, "examples": examples})


class ReadArgs(ToolArgs):
    path: str
    offset: int = 1


class ReadTool(BaseTool[ReadArgs]):
    name = "Read"
    description = ToolDescription.model_validate(DESCRIPTION)
    args_model = ReadArgs

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[ReadArgs] = []

    async def execute(self, args: ReadArgs) -> ToolResult | str:
        self.calls.append(args)
        return f"Read {args.path} from {args.offset}"


def run_tool(tool: ReadTool, arguments: str) -> ToolResult:
    return asyncio.run(tool.run(arguments))


def test_spec_is_an_openai_function_built_from_the_args_model() -> None:
    assert ReadTool().spec == {
        "type": "function",
        "function": {
            "name": "Read",
            "description": ToolDescription.model_validate(DESCRIPTION).render(),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }


def test_spec_is_byte_identical_across_instances() -> None:
    assert json.dumps(ReadTool().spec) == json.dumps(ReadTool().spec)


def test_valid_arguments_run_the_tool() -> None:
    tool = ReadTool()
    result = run_tool(tool, '{"path": "app/page.tsx", "offset": 200}')

    assert result == ToolResult("Read app/page.tsx from 200")
    assert tool.calls == [ReadArgs(path="app/page.tsx", offset=200)]


def test_malformed_json_is_an_error_and_the_tool_does_not_run() -> None:
    tool = ReadTool()
    result = run_tool(tool, '{"path":}')

    assert result.is_error
    assert result.content.startswith("Error (invalid_arguments)")
    assert tool.calls == []


def test_a_missing_argument_is_an_error_and_the_tool_does_not_run() -> None:
    tool = ReadTool()
    result = run_tool(tool, "{}")

    assert result.is_error
    assert "path" in result.content
    assert tool.calls == []


def test_a_wrong_type_is_an_error_and_is_not_repaired() -> None:
    # Strict: the string "5" is not turned into the number 5 (ch04 §4.6, no "smart repair")
    tool = ReadTool()
    result = run_tool(tool, '{"path": "a.tsx", "offset": "5"}')

    assert result.is_error
    assert "offset" in result.content
    assert tool.calls == []


def test_an_invented_argument_is_an_error_and_is_not_ignored() -> None:
    tool = ReadTool()
    result = run_tool(tool, '{"path": "a.tsx", "pth": "b"}')

    assert result.is_error
    assert "pth" in result.content
    assert tool.calls == []


@pytest.mark.parametrize("path", ["“a”.tsx", "trang chủ.tsx", "  a.tsx  "])
def test_arguments_reach_the_tool_byte_for_byte(path: str) -> None:
    # Curly quotes, non-ASCII text and edge whitespace are never normalised (ch04 §4.2.3)
    tool = ReadTool()
    run_tool(tool, json.dumps({"path": path}, ensure_ascii=False))

    assert tool.calls[0].path == path


class MissingFileTool(ReadTool):
    async def execute(self, args: ReadArgs) -> ToolResult | str:
        raise ToolError(f"{args.path} does not exist", "Use Glob to find the right path.")


def test_a_tool_error_becomes_an_observation_with_the_tools_hint() -> None:
    result = run_tool(MissingFileTool(), '{"path": "a.tsx"}')

    assert result == ToolResult(
        "Error (tool_error): a.tsx does not exist\nHint: Use Glob to find the right path.",
        is_error=True,
    )


class RawResultTool(ReadTool):
    async def execute(self, args: ReadArgs) -> ToolResult:
        return ToolResult("raw", is_error=True)


def test_a_tool_result_is_passed_through_unchanged() -> None:
    assert run_tool(RawResultTool(), '{"path": "a.tsx"}') == ToolResult("raw", is_error=True)
