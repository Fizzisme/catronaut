"""Ollama-backed implementation of `ModelProvider`."""

import json
import logging
import re
from typing import Any

import httpx

from app.core.exceptions import ProviderError
from app.core.model_provider.base import ModelProvider, RunUsage

logger = logging.getLogger(__name__)

# Handles TWO different shapes, which is why it matches through the first `</think>` rather
# than a balanced pair:
#   - `qwen3:4b` ignores Ollama's `think: false` and emits reasoning inline terminated by a
#     BARE closing tag with no matching opening tag (measured 2026-08-31). A defect.
#   - `qwen3.8-27b` emits properly delimited `<think>\n...\n</think>\n\n` by design — thinking
#     is on by default there, with tunable `reasoning_effort`
#     (docs/qwen3.8-27b-reference.md). Not a defect; the same strip still yields the answer.
# Either way, everything up to and including that tag is reasoning, not an answer.
_LEAKED_THINK = re.compile(r"^.*?</think>\s*", re.DOTALL)


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        base_url: str,
        model_name: str,
        *,
        num_ctx: int,
        timeout_s: float,
        think: bool = False,
    ):
        self.model_name = model_name
        self._num_ctx = num_ctx
        self._think = think
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_s, connect=10.0),
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        think: bool | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "think": self._think if think is None else think,
            "options": {"num_ctx": self._num_ctx, **options},
        }
        if tools:
            payload["tools"] = [self._as_ollama_tool(tool) for tool in tools]

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Model request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Model backend returned {exc.response.status_code}: "
                f"{exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot reach model backend: {exc}") from exc

    @staticmethod
    def _as_ollama_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Wrap `ToolRegistry.schema()`'s neutral entry in Ollama's function envelope.

        The registry stays backend-agnostic (ROADMAP M2.1), so the request shape is
        applied here — the same rule that keeps response-shape knowledge in the provider.
        An entry that already carries a `function` key is passed through untouched.
        """
        if "function" in tool:
            return tool
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            },
        }

    def extract_tool_calls(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        message = raw.get("message")
        if not isinstance(message, dict):
            return []

        calls = []
        for entry in message.get("tool_calls") or []:
            function = entry.get("function") if isinstance(entry, dict) else None
            if not isinstance(function, dict):
                continue
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                # Ollama sends a dict; OpenAI-compatible backends send a JSON string.
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            calls.append({"name": function.get("name"), "arguments": arguments})
        return calls

    def extract_content(self, raw: dict[str, Any]) -> str:
        message = raw.get("message")
        if not isinstance(message, dict):
            raise ProviderError(f"Unexpected response shape from Ollama: {raw!r:.300}")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Model returned an empty response")

        cleaned = _LEAKED_THINK.sub("", content).strip() if "</think>" in content else content.strip()
        if not cleaned:
            raise ProviderError("Model returned reasoning only, with no answer")
        return cleaned

    def extract_assistant_message(self, raw: dict[str, Any]) -> dict[str, Any]:
        message = raw.get("message")
        if not isinstance(message, dict):
            raise ProviderError(f"Unexpected response shape from Ollama: {raw!r:.300}")

        # Content is passed through UNSTRIPPED — see the base-class docstring. Ollama also
        # splits reasoning into `message.thinking` when the model honours `think: true`, so
        # carry that too when present rather than losing it on the way back into history.
        assistant: dict[str, Any] = {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
        }
        if message.get("thinking"):
            assistant["thinking"] = message["thinking"]
        if message.get("tool_calls"):
            assistant["tool_calls"] = message["tool_calls"]
        return assistant

    def extract_usage(self, raw: dict[str, Any]) -> RunUsage:
        # total_duration is nanoseconds covering the whole request (load + prompt eval + eval) —
        # matches wall-clock latency observed in practice (see CLAUDE.md §3 measurements).
        return RunUsage(
            prompt_tokens=raw.get("prompt_eval_count", 0),
            response_tokens=raw.get("eval_count", 0),
            duration_s=raw.get("total_duration", 0) / 1e9,
        )

    async def health(self) -> bool:
        """True when the Ollama server answers. Used by GET /health."""
        try:
            response = await self._client.get("/api/version", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
