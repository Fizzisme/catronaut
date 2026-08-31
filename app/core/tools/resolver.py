"""One model response in, one validated tool call out (ROADMAP M2.2).

Wraps the pure parsing in `parsing.py` with the milestone's one piece of I/O: **exactly
one** repair turn when the model's call does not validate. Never a loop — a small model
that got the envelope wrong once will usually get it wrong the same way again, and each
attempt costs 20–40s on the dev box.

Path selection is `ModelProfile.tool_call_style`, never a model-name check
(CLAUDE.md §5).
"""

import logging

from app.core.exceptions import ProviderError
from app.core.model_profile import ToolCallStyle
from app.core.model_provider.base import ModelProvider
from app.core.run_context import RunContext
from app.core.tools.parsing import (
    NoToolCall,
    ParseResult,
    ToolCallFailure,
    parse_envelope,
    validate_call,
)
from app.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Fed back verbatim on the single repair turn. Short on purpose: it competes with the
# task for the 4B's window, and a long correction makes the model re-reason from scratch.
REPAIR_PROMPT = (
    "That was not a valid tool call. {reason}\n"
    'Reply with ONLY this JSON object and nothing else:\n'
    '{{"tool": "<tool name>", "args": {{"<arg>": "<value>"}}}}'
)


class ToolCallResolver:
    def __init__(
        self,
        model_provider: ModelProvider,
        registry: ToolRegistry,
        *,
        style: ToolCallStyle,
    ):
        self.model_provider = model_provider
        self.registry = registry
        self.style = style

    async def resolve(
        self,
        run: RunContext,
        messages: list[dict],
        raw: dict,
    ) -> ParseResult:
        """Resolve one model response into a `ToolCall`, `NoToolCall`, or `ToolCallFailure`.

        `messages` is the list that produced `raw`; it is needed to build the repair turn.
        """
        if self.style == "none":
            return NoToolCall(content=self.model_provider.extract_content(raw))

        candidate = self._candidate(raw)
        if candidate is None:
            # No attempted call. The model answered directly, which is a valid outcome.
            return NoToolCall(content=self._content(raw))

        result = validate_call(candidate, self.registry)
        if not isinstance(result, ToolCallFailure):
            logger.info("run_id=%s tool_call name=%s", run.run_id, result.name)
            return result

        logger.info(
            "run_id=%s tool_call invalid (%s) — one repair turn",
            run.run_id,
            result.detail or result.reason,
        )
        return await self._repair(run, messages, raw, result)

    async def _repair(
        self,
        run: RunContext,
        messages: list[dict],
        raw: dict,
        failure: ToolCallFailure,
    ) -> ParseResult:
        repair_messages = [
            *messages,
            {"role": "assistant", "content": self._content(raw, allow_empty=True)},
            {"role": "user", "content": REPAIR_PROMPT.format(reason=failure.reason)},
        ]
        repaired_raw = await self.model_provider.chat(
            messages=repair_messages,
            tools=self.registry.schema() if self.style == "native" else None,
        )

        candidate = self._candidate(repaired_raw)
        if candidate is None:
            # It answered in prose instead of repairing. Prose beats a hard failure.
            logger.info("run_id=%s tool_call repair returned prose", run.run_id)
            return NoToolCall(content=self._content(repaired_raw))

        result = validate_call(candidate, self.registry)
        if isinstance(result, ToolCallFailure):
            logger.warning(
                "run_id=%s tool_call repair failed (%s) — giving up",
                run.run_id,
                result.detail or result.reason,
            )
        else:
            logger.info("run_id=%s tool_call name=%s (repaired)", run.run_id, result.name)
        return result

    def _candidate(self, raw: dict) -> dict | None:
        """The attempted call in a raw response, or None when there is none."""
        if self.style == "native":
            calls = self.model_provider.extract_tool_calls(raw)
            if calls:
                if len(calls) > 1:
                    # The loop (M5.2) executes one call per iteration; the rest would be
                    # acted on with a stale context anyway.
                    logger.info("dropping %d extra tool call(s) from one response", len(calls) - 1)
                return calls[0]
            return None

        content = self._content(raw)
        return parse_envelope(content) if content else None

    def _content(self, raw: dict, *, allow_empty: bool = False) -> str:
        """Assistant text, tolerating the empty content that accompanies a native call.

        Measured on `qwen3:4b` (2026-08-31): on the native path the content after its
        leaked `</think>` block is empty, and `extract_content` raises on that by design.
        """
        try:
            return self.model_provider.extract_content(raw)
        except ProviderError:
            if allow_empty:
                return ""
            raise
