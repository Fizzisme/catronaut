"""Tests for M2.2 — tool-call parsing, validation, and the one repair turn.

The model is stubbed. The envelope and the leaked-`</think>` shapes asserted here are
copied from a real `qwen3:4b` probe on 2026-08-31 (recorded in ROADMAP M2.2), so these
are regression tests against measured behaviour, not invented strings.
"""

import pytest
from pydantic import BaseModel

from app.core.model_provider.base import ModelProvider, RunUsage
from app.core.model_provider.ollama_provider import OllamaProvider
from app.core.model_profile import get_model_profile
from app.core.run_context import RunContext
from app.core.tools.base import Tool
from app.core.tools.parsing import (
    NoToolCall,
    ToolCall,
    ToolCallFailure,
    build_tool_instructions,
    parse_envelope,
    validate_call,
)
from app.core.tools.registry import ToolRegistry
from app.core.tools.resolver import ToolCallResolver


class _ContrastArgs(BaseModel):
    foreground: str
    background: str


class _ContrastTool(Tool):
    name = "check_contrast"
    description = "Check the WCAG contrast ratio between two hex colors."
    args_schema = _ContrastArgs
    read_only = True

    async def run(self, args: _ContrastArgs) -> str:
        return f"{args.foreground} on {args.background}"


@pytest.fixture
def registry():
    return ToolRegistry([_ContrastTool()])


@pytest.fixture
def run():
    return RunContext(domain="ui_ux", model_profile=get_model_profile("qwen3:4b"))


class _ScriptedProvider(ModelProvider):
    """Returns queued responses and counts calls, so "exactly one repair" is testable."""

    def __init__(self, *responses: dict):
        self._responses = list(responses)
        self.calls = 0
        self.last_tools = None

    async def chat(self, messages, *, tools=None, think=None, **options):
        self.calls += 1
        self.last_tools = tools
        return self._responses.pop(0)

    def extract_content(self, raw):
        return OllamaProvider.extract_content(self, raw)

    def extract_tool_calls(self, raw):
        return OllamaProvider.extract_tool_calls(self, raw)

    def extract_usage(self, raw):
        return RunUsage(prompt_tokens=1, response_tokens=1, duration_s=0.01)

    async def aclose(self) -> None:
        return None


def _native(name: str, arguments: dict, content: str = "") -> dict:
    return {
        "model": "qwen3:4b",
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": [{"id": "call_x", "function": {"name": name, "arguments": arguments}}],
        },
    }


def _text(content: str) -> dict:
    return {"model": "qwen3:4b", "message": {"role": "assistant", "content": content}}


# --- pure parsing ------------------------------------------------------------

def test_parse_envelope_handles_the_measured_4b_shape():
    # Verbatim from the probe: reasoning, a bare closing tag, then the envelope.
    content = (
        "Okay, let me tackle this. The user wants contrast checked.\n"
        "</think>\n\n"
        '{"tool": "check_contrast", "args": {"foreground": "#999999", "background": "#ffffff"}}'
    )
    assert parse_envelope(content) == {
        "name": "check_contrast",
        "arguments": {"foreground": "#999999", "background": "#ffffff"},
    }


def test_parse_envelope_strips_code_fences():
    content = '```json\n{"tool": "check_contrast", "args": {"foreground": "#000", "background": "#fff"}}\n```'
    assert parse_envelope(content)["name"] == "check_contrast"


def test_parse_envelope_ignores_braces_inside_strings():
    content = '{"tool": "check_contrast", "args": {"foreground": "#fff", "background": "}{"}}'
    assert parse_envelope(content)["arguments"]["background"] == "}{"


def test_parse_envelope_returns_none_for_prose():
    assert parse_envelope("Visual hierarchy is the arrangement of elements.") is None


def test_parse_envelope_returns_none_for_json_that_is_not_an_envelope():
    assert parse_envelope('Here is data: {"foreground": "#fff"}') is None


def test_validate_call_rejects_an_unknown_tool_name(registry):
    result = validate_call({"name": "check_colours", "arguments": {}}, registry)
    assert isinstance(result, ToolCallFailure)
    assert "check_contrast" in result.reason  # tells the model what it can call


def test_validate_call_rejects_bad_args(registry):
    result = validate_call({"name": "check_contrast", "arguments": {"foreground": "#fff"}}, registry)
    assert isinstance(result, ToolCallFailure)
    assert "background" in result.reason
    assert "\n" not in result.reason  # one line: it re-enters the model's context


def test_validate_call_returns_a_validated_args_instance(registry):
    result = validate_call(
        {"name": "check_contrast", "arguments": {"foreground": "#999999", "background": "#ffffff"}},
        registry,
    )
    assert isinstance(result, ToolCall)
    assert isinstance(result.args, _ContrastArgs)
    assert result.args.foreground == "#999999"


def test_build_tool_instructions_lists_the_tool_and_the_envelope(registry):
    text = build_tool_instructions(registry)
    assert "check_contrast(foreground, background)" in text
    assert '{"tool": "<tool name>"' in text


# --- resolver: native path ---------------------------------------------------

@pytest.mark.asyncio
async def test_native_path_reads_structured_calls(registry, run):
    provider = _ScriptedProvider()
    resolver = ToolCallResolver(provider, registry, style="native")

    raw = _native("check_contrast", {"foreground": "#999999", "background": "#ffffff"})
    result = await resolver.resolve(run, [], raw)

    assert isinstance(result, ToolCall)
    assert result.args.background == "#ffffff"
    assert provider.calls == 0  # no repair needed


@pytest.mark.asyncio
async def test_native_path_tolerates_empty_content_beside_a_tool_call(registry, run):
    """Measured: on the native path the 4B leaves content empty after `</think>`, which
    `extract_content` raises on. Resolving a tool call must not go through it."""
    provider = _ScriptedProvider()
    resolver = ToolCallResolver(provider, registry, style="native")

    raw = _native("check_contrast", {"foreground": "#999999", "background": "#ffffff"},
                  content="Okay, the user wants contrast checked.\n</think>\n\n")
    assert isinstance(await resolver.resolve(run, [], raw), ToolCall)


# --- resolver: prompt path and terminal states -------------------------------

@pytest.mark.asyncio
async def test_prompt_path_parses_the_envelope(registry, run):
    provider = _ScriptedProvider()
    resolver = ToolCallResolver(provider, registry, style="prompt")

    raw = _text(
        "Okay, the user gave both colors.\n</think>\n\n"
        '{"tool": "check_contrast", "args": {"foreground": "#999999", "background": "#ffffff"}}'
    )
    result = await resolver.resolve(run, [], raw)
    assert isinstance(result, ToolCall)


@pytest.mark.asyncio
async def test_a_direct_answer_is_a_valid_terminal_state_not_an_error(registry, run):
    provider = _ScriptedProvider()
    resolver = ToolCallResolver(provider, registry, style="prompt")

    raw = _text("Reasoning.\n</think>\n\nVisual hierarchy guides attention.")
    result = await resolver.resolve(run, [], raw)

    assert isinstance(result, NoToolCall)
    assert result.content == "Visual hierarchy guides attention."
    assert provider.calls == 0


# --- resolver: the one bounded repair turn -----------------------------------

@pytest.mark.asyncio
async def test_invalid_args_trigger_exactly_one_repair_that_can_succeed(registry, run):
    provider = _ScriptedProvider(
        _text('{"tool": "check_contrast", "args": {"foreground": "#999999", "background": "#ffffff"}}')
    )
    resolver = ToolCallResolver(provider, registry, style="prompt")

    raw = _text('{"tool": "check_contrast", "args": {"foreground": "#999999"}}')
    result = await resolver.resolve(run, [{"role": "user", "content": "check it"}], raw)

    assert isinstance(result, ToolCall)
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_repair_is_never_looped(registry, run):
    """Two bad responses in a row must surface a failure, not a third attempt."""
    bad = '{"tool": "check_contrast", "args": {"foreground": "#999999"}}'
    provider = _ScriptedProvider(_text(bad), _text(bad))
    resolver = ToolCallResolver(provider, registry, style="prompt")

    result = await resolver.resolve(run, [{"role": "user", "content": "check it"}], _text(bad))

    assert isinstance(result, ToolCallFailure)
    assert provider.calls == 1  # one repair, then give up


@pytest.mark.asyncio
async def test_unknown_tool_name_is_repaired_the_same_way(registry, run):
    provider = _ScriptedProvider(
        _text('{"tool": "check_contrast", "args": {"foreground": "#111", "background": "#fff"}}')
    )
    resolver = ToolCallResolver(provider, registry, style="prompt")

    raw = _text('{"tool": "check_colours", "args": {"foreground": "#111", "background": "#fff"}}')
    result = await resolver.resolve(run, [], raw)

    assert isinstance(result, ToolCall)
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_prose_on_the_repair_turn_beats_a_hard_failure(registry, run):
    provider = _ScriptedProvider(_text("Reasoning.\n</think>\n\nThe contrast is too low."))
    resolver = ToolCallResolver(provider, registry, style="prompt")

    raw = _text('{"tool": "check_contrast", "args": {"foreground": "#999999"}}')
    result = await resolver.resolve(run, [], raw)

    assert isinstance(result, NoToolCall)
    assert result.content == "The contrast is too low."


@pytest.mark.asyncio
async def test_style_none_never_looks_for_a_tool_call(registry, run):
    provider = _ScriptedProvider()
    resolver = ToolCallResolver(provider, registry, style="none")

    raw = _text('{"tool": "check_contrast", "args": {"foreground": "#111", "background": "#fff"}}')
    result = await resolver.resolve(run, [], raw)

    assert isinstance(result, NoToolCall)


# --- provider-side shapes ----------------------------------------------------

def test_ollama_provider_wraps_registry_schema_into_the_function_envelope(registry):
    [wrapped] = [OllamaProvider._as_ollama_tool(entry) for entry in registry.schema()]
    assert wrapped["type"] == "function"
    assert wrapped["function"]["name"] == "check_contrast"
    assert "foreground" in wrapped["function"]["parameters"]["properties"]


def test_ollama_provider_passes_through_an_already_wrapped_tool():
    already = {"type": "function", "function": {"name": "x", "parameters": {}}}
    assert OllamaProvider._as_ollama_tool(already) is already


def test_ollama_provider_parses_json_string_arguments():
    provider = _ScriptedProvider()
    raw = {
        "message": {
            "tool_calls": [{"function": {"name": "check_contrast", "arguments": '{"foreground": "#111"}'}}]
        }
    }
    assert provider.extract_tool_calls(raw) == [
        {"name": "check_contrast", "arguments": {"foreground": "#111"}}
    ]


def test_ollama_provider_returns_no_tool_calls_for_a_plain_answer():
    provider = _ScriptedProvider()
    assert provider.extract_tool_calls(_text("just text")) == []
