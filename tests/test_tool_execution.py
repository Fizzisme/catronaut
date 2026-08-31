"""Tests for M2.3 — execution policy: allowlist, per-tool timeout, result truncation.

No model involved — `ToolCall` instances are built directly, the way M2.2's resolver
would hand them to the executor after validation.
"""

import asyncio

import pytest
from pydantic import BaseModel

from app.core.model_profile import get_model_profile
from app.core.run_context import RunContext
from app.core.tools.base import Tool
from app.core.tools.executor import ToolExecutor
from app.core.tools.parsing import ToolCall
from app.core.tools.policy import ToolPolicy
from app.core.tools.registry import ToolRegistry


class _EchoArgs(BaseModel):
    text: str = "hi"


class _EchoTool(Tool):
    name = "echo"
    description = "Echo text back."
    args_schema = _EchoArgs
    read_only = True

    async def run(self, args: _EchoArgs) -> str:
        return args.text


class _WriteTool(Tool):
    name = "write_file"
    description = "Pretend to write a file."
    args_schema = _EchoArgs
    read_only = False

    async def run(self, args: _EchoArgs) -> str:
        return f"wrote {args.text}"


class _SlowTool(Tool):
    name = "slow"
    description = "Sleeps longer than its timeout."
    args_schema = _EchoArgs
    read_only = True
    timeout_s = 0.05

    async def run(self, args: _EchoArgs) -> str:
        await asyncio.sleep(1.0)
        return "should not get here"


class _BrokenTool(Tool):
    name = "broken"
    description = "Always raises."
    args_schema = _EchoArgs
    read_only = True

    async def run(self, args: _EchoArgs) -> str:
        raise ValueError("boom")


class _BigTool(Tool):
    name = "big"
    description = "Returns a huge result."
    args_schema = _EchoArgs
    read_only = True

    async def run(self, args: _EchoArgs) -> str:
        return "x" * 5000


@pytest.fixture
def registry():
    return ToolRegistry([_EchoTool(), _WriteTool(), _SlowTool(), _BrokenTool(), _BigTool()])


@pytest.fixture
def run():
    return RunContext(domain="ui_ux", model_profile=get_model_profile("qwen3:4b"))


def _call(name: str, **args) -> ToolCall:
    args_model = _EchoArgs(**args) if args else _EchoArgs()
    return ToolCall(name=name, args=args_model, raw_args=args)


@pytest.mark.asyncio
async def test_allowed_tool_runs_and_returns_success(registry, run):
    policy = ToolPolicy(allowed_tools=frozenset({"echo"}))
    executor = ToolExecutor(registry, policy)

    result = await executor.execute(run, _call("echo", text="hello"))

    assert result.success is True
    assert result.output == "hello"
    assert result.truncated is False
    assert result.denied_reason is None


@pytest.mark.asyncio
async def test_disallowed_tool_is_denied_without_running(registry, run):
    policy = ToolPolicy(allowed_tools=frozenset({"echo"}))  # write_file NOT allowed
    executor = ToolExecutor(registry, policy)

    result = await executor.execute(run, _call("write_file", text="secret"))

    assert result.success is False
    assert result.denied_reason is not None
    assert "write_file" in result.denied_reason
    assert "ui_ux" in result.denied_reason


@pytest.mark.asyncio
async def test_timeout_is_caught_and_reported(registry, run):
    policy = ToolPolicy.allow_all(registry)
    executor = ToolExecutor(registry, policy)

    result = await executor.execute(run, _call("slow"))

    assert result.success is False
    assert "timed out" in result.output


@pytest.mark.asyncio
async def test_a_tool_exception_never_escapes_the_executor(registry, run):
    policy = ToolPolicy.allow_all(registry)
    executor = ToolExecutor(registry, policy)

    result = await executor.execute(run, _call("broken"))

    assert result.success is False
    assert "boom" in result.output


@pytest.mark.asyncio
async def test_oversized_result_is_truncated(registry, run):
    policy = ToolPolicy.allow_all(registry)
    executor = ToolExecutor(registry, policy, max_result_chars=100)

    result = await executor.execute(run, _call("big"))

    assert result.truncated is True
    assert len(result.output) <= 100 + len("\n...[truncated]")
    assert result.output.endswith("[truncated]")


@pytest.mark.asyncio
async def test_result_is_appended_to_run_context_tool_results(registry, run):
    policy = ToolPolicy.allow_all(registry)
    executor = ToolExecutor(registry, policy)

    assert run.tool_results == []
    result = await executor.execute(run, _call("echo", text="hi"))

    assert run.tool_results == [result]


@pytest.mark.asyncio
async def test_denied_call_is_also_appended_to_run_context(registry, run):
    policy = ToolPolicy(allowed_tools=frozenset())
    executor = ToolExecutor(registry, policy)

    await executor.execute(run, _call("echo", text="hi"))

    assert len(run.tool_results) == 1
    assert run.tool_results[0].denied_reason is not None


def test_policy_allow_all_includes_every_registered_tool(registry):
    policy = ToolPolicy.allow_all(registry)
    assert policy.is_allowed("echo")
    assert policy.is_allowed("write_file")
    assert not policy.is_allowed("not_registered")
