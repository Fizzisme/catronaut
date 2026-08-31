"""Unit tests for the M2.1 Tool abstraction and registry. No model calls
involved — parsing model tool-call output is M2.2, a real tool pack is M2.4."""

import pytest
from pydantic import BaseModel

from app.core.tools.base import Tool
from app.core.tools.registry import ToolRegistry


class _EchoArgs(BaseModel):
    text: str


class _EchoTool(Tool):
    name = "echo_text"
    description = "Echo the given text back."
    args_schema = _EchoArgs
    read_only = True

    async def run(self, args: _EchoArgs) -> str:
        return args.text


class _OtherArgs(BaseModel):
    value: int


class _OtherTool(Tool):
    name = "double_value"
    description = "Double an integer."
    args_schema = _OtherArgs
    read_only = True

    async def run(self, args: _OtherArgs) -> int:
        return args.value * 2


def test_registry_resolves_tool_by_name():
    registry = ToolRegistry([_EchoTool(), _OtherTool()])
    assert isinstance(registry.get("echo_text"), _EchoTool)
    assert registry.get("missing_tool") is None


def test_registry_schema_includes_name_description_parameters():
    registry = ToolRegistry([_EchoTool()])
    [schema] = registry.schema()
    assert schema["name"] == "echo_text"
    assert schema["description"] == "Echo the given text back."
    assert schema["parameters"]["properties"]["text"]["type"] == "string"


def test_registry_rejects_duplicate_tool_names():
    with pytest.raises(ValueError):
        ToolRegistry([_EchoTool(), _EchoTool()])


def test_registry_len_and_iter():
    registry = ToolRegistry([_EchoTool(), _OtherTool()])
    assert len(registry) == 2
    assert {tool.name for tool in registry} == {"echo_text", "double_value"}


@pytest.mark.asyncio
async def test_tool_run_receives_validated_args():
    tool = _EchoTool()
    result = await tool.run(_EchoArgs(text="hi"))
    assert result == "hi"
