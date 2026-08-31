"""Turning a model response into a validated tool call (ROADMAP M2.2).

Two paths, chosen by `ModelProfile.tool_call_style`:

- **native** — the backend returns structured calls; the provider normalizes them
  (`ModelProvider.extract_tool_calls`).
- **prompt** — the model is told to emit a JSON envelope in its text, which is pulled
  back out here with a tolerant parser.

Everything in this module is pure: text and dicts in, dataclasses out, no I/O. The one
bounded repair turn needs a model call and therefore lives in `resolver.py`.

**The frozen envelope** (measured against `qwen3:4b` on 2026-08-31 — it emits exactly
this, unfenced, after its leaked `</think>` block):

    {"tool": "check_contrast", "args": {"foreground": "#999999", "background": "#ffffff"}}

Do not change that shape casually: ROADMAP M7.3 plans to fine-tune on it, and M5.2's
loop branches on the result types below.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Union

from pydantic import BaseModel, ValidationError

from app.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ```json ... ``` or ``` ... ``` around the envelope. The 4B did not fence its output in
# testing, but a fenced variant is the single most likely drift, so it is tolerated.
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclass(frozen=True)
class ToolCall:
    """A call that named a registered tool and passed its `args_schema`."""

    name: str
    args: BaseModel
    raw_args: dict


@dataclass(frozen=True)
class NoToolCall:
    """The model answered directly. A valid terminal state, never an error — the 4B
    often answers when it could have called a tool, and that answer is still usable
    (ROADMAP M5.2)."""

    content: str


@dataclass(frozen=True)
class ToolCallFailure:
    """The model tried to call a tool and got it wrong, and the one repair turn did not
    fix it. `reason` is fed back to the model, so it stays one short line."""

    reason: str
    detail: str = ""


ParseResult = Union[ToolCall, NoToolCall, ToolCallFailure]


def build_tool_instructions(registry: ToolRegistry) -> str:
    """The prompt-path envelope instructions for the registry's tools.

    Returned as text rather than injected anywhere: who owns system prompt composition
    is still an open question (see ROADMAP "Still open"), and this milestone should not
    settle it by accident.
    """
    lines = ["You have these tools:"]
    for schema in registry.schema():
        params = schema["parameters"].get("properties", {})
        signature = ", ".join(params)
        lines.append(f"- {schema['name']}({signature}) — {schema['description']}")
    lines.extend(
        [
            "",
            "To use a tool, reply with ONLY this JSON object and nothing else:",
            '{"tool": "<tool name>", "args": {"<arg>": "<value>"}}',
            "",
            "If no tool is needed, reply with plain text. Never mix text and JSON.",
        ]
    )
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    match = _FENCE.search(text)
    return match.group(1) if match else text


def _first_balanced_object(text: str) -> str | None:
    """The first `{...}` that balances, ignoring braces inside strings.

    `json.loads` on the whole message would fail on the reasoning prose the 4B leaves
    around its answer, and a greedy regex would swallow trailing text.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        start = text.find("{", start + 1)
    return None


def parse_envelope(text: str) -> dict[str, Any] | None:
    """Pull a `{"tool", "args"}` envelope out of model text.

    Returns the normalized `{"name", "arguments"}` shape, or `None` when the text holds
    no attempted call — prose, or JSON that is not an envelope. `None` means "the model
    answered"; it never means "the model failed".
    """
    candidate = _first_balanced_object(_strip_fences(text))
    if candidate is None:
        return None

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict) or "tool" not in parsed:
        return None

    return {"name": parsed.get("tool"), "arguments": parsed.get("args", {})}


def validate_call(candidate: dict[str, Any], registry: ToolRegistry) -> ParseResult:
    """Check an attempted call against the registry and the tool's `args_schema`."""
    name = candidate.get("name")
    if not isinstance(name, str) or not name:
        return ToolCallFailure(reason="The tool call is missing a tool name.")

    tool = registry.get(name)
    if tool is None:
        available = ", ".join(schema["name"] for schema in registry.schema())
        return ToolCallFailure(
            reason=f"There is no tool named {name!r}. Available tools: {available}.",
            detail=f"unknown tool name={name!r}",
        )

    arguments = candidate.get("arguments")
    if not isinstance(arguments, dict):
        return ToolCallFailure(
            reason=f"The args for {name!r} must be a JSON object.",
            detail=f"args was {type(arguments).__name__}",
        )

    try:
        args = tool.args_schema(**arguments)
    except ValidationError as exc:
        return ToolCallFailure(
            reason=f"The args for {name!r} are invalid: {_summarize(exc)}",
            detail=str(exc),
        )

    return ToolCall(name=name, args=args, raw_args=arguments)


def _summarize(exc: ValidationError) -> str:
    """A one-line summary of a pydantic error.

    It is fed back to the model for its single repair turn, and on the 4B every token
    of it competes with the actual task, so at most two problems are reported.
    """
    parts = []
    for error in exc.errors()[:2]:
        field = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{field}: {error['msg']}")
    return "; ".join(parts)
