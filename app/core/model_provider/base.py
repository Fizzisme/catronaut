"""The contract every model backend must satisfy.

Everything downstream (agents, and later the tool layer and the agent loop) binds
to this interface rather than to Ollama, so a second backend can be added without
touching domain code.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# Shared by every backend, because it is a property of the Qwen family rather than of any
# one server. Two shapes reach us:
#   - `qwen3:4b` ignores the think flag and leaks reasoning terminated by a BARE `</think>`
#     with no opening tag (measured 2026-08-31).
#   - `qwen3.8-27b` emits properly delimited `<think>\n...\n</think>\n\n` by design
#     (docs/qwen3.8-27b-reference.md).
# Matching through the FIRST closing tag handles both without needing a balanced pair.
_LEAKED_THINK = re.compile(r"^.*?</think>\s*", re.DOTALL)


def strip_thinking(content: str) -> str:
    """Reasoning removed, for a user-facing response body.

    Never use this to build conversation history — see `extract_assistant_message`.
    """
    if "</think>" not in content:
        return content.strip()
    return _LEAKED_THINK.sub("", content).strip()


@dataclass(frozen=True)
class RunUsage:
    prompt_tokens: int
    response_tokens: int
    duration_s: float


class ModelProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        think: bool | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Run one chat completion and return the backend's raw response payload.

        `think` defaults to the configured value when None. `options` are passed
        through to the backend as generation options (temperature, num_ctx, ...).
        """

    @abstractmethod
    async def aclose(self) -> None:
        """Release network resources. Called on application shutdown."""

    def extract_content(self, raw: dict[str, Any]) -> str:
        """Pull the assistant's user-facing text out of a raw response.

        Overridden per backend so agents never reach into provider-shaped dicts.
        """
        raise NotImplementedError

    def extract_tool_calls(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Structured tool calls from a raw response, normalized to
        `[{"name": str, "arguments": dict}]`. Empty list when the model made none.

        Same reasoning as `extract_content`: where the calls live in the payload
        (Ollama nests them under `message.tool_calls[].function`) is backend-specific
        and must not leak into the tool layer. See ROADMAP M2.2.
        """
        raise NotImplementedError

    def extract_assistant_message(self, raw: dict[str, Any]) -> dict[str, Any]:
        """The assistant's turn **as it should be re-sent in history**, not as shown to a user.

        Distinct from `extract_content` on purpose, and the distinction is load-bearing:
        `extract_content` strips the model's `<think>` block, which is right for a response
        body and wrong for a conversation turn. `qwen3.8-27b` enables `preserve_thinking` by
        default and expects the thinking from *all* prior messages back
        (docs/qwen3.8-27b-reference.md), so building history out of `extract_content` would
        silently discard exactly what that model wants retained — and would also undercount
        the turn against M4.1's budget, since the hidden part still occupies context.

        Returns the message with reasoning INTACT and any `tool_calls` preserved. Whether to
        keep or drop the thinking is policy, decided by the caller from
        `ModelProfile.retains_thinking_in_history` — this method only reports the shape,
        which is backend-specific, exactly like the other `extract_*` methods.
        """
        raise NotImplementedError

    def extract_usage(self, raw: dict[str, Any]) -> RunUsage:
        """Pull token/latency metrics out of a raw response. See extract_content — same reason:
        metric field names (e.g. Ollama's `prompt_eval_count` vs. an OpenAI-style `usage.
        prompt_tokens`) are backend-specific and must not leak into agents or RunContext."""
        raise NotImplementedError

    async def health(self) -> bool:
        """True when the backend answers. Used by GET /health, so every provider needs it."""
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts for retrieval. Implemented when RAG lands (ROADMAP M6.3)."""
        raise NotImplementedError("Embeddings are not implemented yet (ROADMAP M6.3)")
