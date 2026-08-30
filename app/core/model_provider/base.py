"""The contract every model backend must satisfy.

Everything downstream (agents, and later the tool layer and the agent loop) binds
to this interface rather than to Ollama, so a second backend can be added without
touching domain code.
"""

from abc import ABC, abstractmethod
from typing import Any


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

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts for retrieval. Implemented when RAG lands (ROADMAP M5.3)."""
        raise NotImplementedError("Embeddings are not implemented yet (ROADMAP M5.3)")
