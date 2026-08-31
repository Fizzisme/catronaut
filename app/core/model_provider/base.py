"""The contract every model backend must satisfy.

Everything downstream (agents, and later the tool layer and the agent loop) binds
to this interface rather than to Ollama, so a second backend can be added without
touching domain code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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

    def extract_usage(self, raw: dict[str, Any]) -> RunUsage:
        """Pull token/latency metrics out of a raw response. See extract_content — same reason:
        metric field names (e.g. Ollama's `prompt_eval_count` vs. an OpenAI-style `usage.
        prompt_tokens`) are backend-specific and must not leak into agents or RunContext."""
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts for retrieval. Implemented when RAG lands (ROADMAP M6.3)."""
        raise NotImplementedError("Embeddings are not implemented yet (ROADMAP M6.3)")
