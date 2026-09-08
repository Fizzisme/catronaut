"""Executes a validated `ToolCall` under M2.3's execution policy: allowlist check,
per-tool timeout, and result-size truncation before the result re-enters context.

Takes a `ToolCall` from `parsing.py` (M2.2) — args are already validated against
`args_schema` — and always returns a `ToolExecutionResult`: denied, timed out, errored,
or succeeded, but never a raised exception and never an unbounded string. The loop
(M5.2) can feed any of those back to the model without special-casing failure.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from app.core.run_context import RunContext
from app.core.token_budget import max_text_bytes
from app.core.tools.parsing import ToolCall
from app.core.tools.policy import ToolPolicy
from app.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Fallback only, for a run with no planned budget (a domain that has not called
# `Agent._plan_budget`, or a unit test constructing a bare `RunContext`). The real limit is
# whatever the window can still hold — see `_result_byte_cap`. This constant used to be the
# *only* limit, which capped every model at 2000 characters: on a 262k-token window that
# truncated a `read_file` of a 500-line source file down to ~60 lines, breaking `site_gen`'s
# editing flow on exactly the model big enough to run it (ROADMAP M2.3 named M4.1 as this
# number's real owner).
DEFAULT_MAX_RESULT_BYTES = 2000

_TRUNCATION_MARKER = "\n...[truncated]"


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    success: bool
    output: str  # always a string, always model-facing, already truncated if needed
    truncated: bool
    duration_s: float
    denied_reason: str | None = None  # set only when the allowlist blocked the call


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        *,
        max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES,
    ):
        self.registry = registry
        self.policy = policy
        self.max_result_bytes = max_result_bytes

    def _result_byte_cap(self, run: RunContext) -> int:
        """How much of one tool result can come back into context.

        Prefers the live per-call budget (M4.1): a result only needs trimming to what the
        window can *still* hold, which on a large-window model is vastly more than the
        fallback constant. `available` already has the system prompt, tool schema, current
        input and the output reservation subtracted, and it shrinks each iteration as
        results accumulate — so capping at it needs no fraction and no per-model tuning.

        Deciding *which* accumulated results to drop once that pool runs dry is M4.3's job,
        not this module's; until it exists an over-budget run falls back to the constant so
        a result is trimmed rather than emptied.
        """
        budget = run.token_budget
        if not budget:
            return self.max_result_bytes
        available = budget.get("available", 0)
        if available <= 0:
            logger.warning(
                "run_id=%s tool result capped at the fallback %d bytes: the run is already "
                "over budget (available=%s). Compaction is M4.3.",
                run.run_id,
                self.max_result_bytes,
                available,
            )
            return self.max_result_bytes
        return max_text_bytes(available)

    async def execute(self, run: RunContext, call: ToolCall) -> ToolExecutionResult:
        if not self.policy.is_allowed(call.name):
            reason = f"{call.name!r} is not allowed for domain {run.domain!r}."
            logger.warning("run_id=%s tool_call denied name=%s", run.run_id, call.name)
            result = ToolExecutionResult(
                tool_name=call.name,
                success=False,
                output=reason,
                truncated=False,
                duration_s=0.0,
                denied_reason=reason,
            )
            run.tool_results.append(result)
            return result

        tool = self.registry.get(call.name)
        # call.name was already checked against the registry by M2.2's validate_call, so
        # a miss here is a programming error (a policy naming a tool that was never
        # registered), not a model mistake.
        assert tool is not None, f"policy allowed a tool not in the registry: {call.name!r}"

        started = time.monotonic()
        try:
            raw_output = await asyncio.wait_for(tool.run(call.args), timeout=tool.timeout_s)
            output = str(raw_output)
            success = True
        except asyncio.TimeoutError:
            output = f"Tool {call.name!r} timed out after {tool.timeout_s}s."
            success = False
            logger.warning(
                "run_id=%s tool_call timeout name=%s timeout_s=%s",
                run.run_id, call.name, tool.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 — a tool's own bug must not crash the run
            output = f"Tool {call.name!r} failed: {exc}"
            success = False
            logger.warning(
                "run_id=%s tool_call error name=%s error=%s", run.run_id, call.name, exc
            )
        duration_s = time.monotonic() - started

        # Trimmed by UTF-8 bytes, not codepoints, to match how `count_tokens` measures —
        # slicing a str by characters could still blow the byte budget on Vietnamese or CJK
        # output. `errors="ignore"` drops a partial character left at the cut.
        cap = self._result_byte_cap(run)
        encoded = output.encode("utf-8")
        truncated = len(encoded) > cap
        if truncated:
            output = encoded[:cap].decode("utf-8", errors="ignore") + _TRUNCATION_MARKER

        result = ToolExecutionResult(
            tool_name=call.name,
            success=success,
            output=output,
            truncated=truncated,
            duration_s=duration_s,
        )
        run.tool_results.append(result)

        # Side-effecting calls get a louder log line — read-only vs side-effecting
        # classification (ROADMAP M2.3) has one consumer today: an audit trail. Actually
        # gating which side-effecting calls are allowed is M8.2, not this module.
        log = logger.warning if not tool.read_only else logger.info
        log(
            "run_id=%s tool_call done name=%s success=%s duration_s=%.2f "
            "truncated=%s read_only=%s",
            run.run_id, call.name, success, duration_s, truncated, tool.read_only,
        )
        return result
