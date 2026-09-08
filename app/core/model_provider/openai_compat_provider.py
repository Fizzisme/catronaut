"""OpenAI-compatible `ModelProvider`, for the production model (ROADMAP M1.6).

**This exists because the prod model is not served by Ollama.** `qwen3.8-27b` ships as
HuggingFace Transformers weights and its card recommends **vLLM, SGLang or TokenSpeed**,
all of which expose an OpenAI-compatible `/v1/chat/completions` endpoint. Ollama is never
mentioned (docs/qwen3.8-27b-reference.md). The long-standing "it needs a Modelfile / private
registry" plan was inferred from Ollama being the only backend this service had, not from
anything the model says.

This is the first real test of M0.2's claim that a second backend can be added without
touching domain code — every `extract_*` method exists precisely so response-shape knowledge
stays here. Differences from `OllamaProvider`, all absorbed in this file:

| | Ollama | here |
|---|---|---|
| endpoint | `/api/chat` | `/v1/chat/completions` |
| message | `raw["message"]` | `raw["choices"][0]["message"]` |
| tool args | a dict | a **JSON string** |
| usage | `prompt_eval_count` / `eval_count` | `usage.prompt_tokens` / `completion_tokens` |
| duration | `total_duration` (ns) | absent — measured client-side |
| images | `message.images` (base64 array) | `image_url` content blocks |
| thinking off | `think: false` | `chat_template_kwargs.enable_thinking` |
| context size | `options.num_ctx` per request | **server launch flag — cannot be sent** |

That last row matters: the window is fixed when the server starts, so M4.1's budget is a
*prediction* of what that server will accept rather than something this provider enforces.
Keep `ModelProfile.context_window` in step with how the server was actually launched.

**Not verified against a live server** — `qwen3.8-27b` is not running anywhere yet (CLAUDE.md
§3). The wire shapes here come from the model card and the OpenAI schema both vLLM and SGLang
implement; treat the first real deployment as the verification step, and re-check
`reasoning_content` in particular, since exposing it separately is a server-level choice.
"""

import json
import logging
import time
from typing import Any

import httpx

from app.core.exceptions import ProviderError
from app.core.model_provider.base import ModelProvider, RunUsage, strip_thinking

logger = logging.getLogger(__name__)


class OpenAICompatProvider(ModelProvider):
    def __init__(
        self,
        base_url: str,
        model_name: str,
        *,
        timeout_s: float,
        api_key: str | None = None,
        think: bool = True,
        reasoning_effort: str | None = None,
    ):
        self.model_name = model_name
        # Qwen3.8 reasons by default, and the card warns that lowering effort in multi-turn
        # agentic work can *raise* total latency through insufficient analysis and retries.
        # So the default here is the model's own default, not the cheapest setting.
        self._think = think
        self._reasoning_effort = reasoning_effort
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_s, connect=10.0),
            headers=headers,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        think: bool | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        thinking = self._think if think is None else think
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [self._as_openai_message(m) for m in messages],
            "stream": False,
            **options,
        }
        if tools:
            payload["tools"] = [self._as_openai_tool(tool) for tool in tools]
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if not thinking:
            # The card's documented off-switch. Deliberately NOT Ollama's `think` flag —
            # a different mechanism on a different API, which is exactly the kind of
            # difference this class exists to absorb.
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        # No `num_ctx` here: an OpenAI-compatible server fixes its context length at launch.
        started = time.monotonic()
        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Model request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            # `exc.response.text` can echo the request; it never contains the API key, which
            # travels in a header, but keep it short regardless.
            raise ProviderError(
                f"Model backend returned {exc.response.status_code}: "
                f"{exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot reach model backend: {exc}") from exc

        # The response carries no timing of its own, unlike Ollama's `total_duration`, so
        # measure it here — `extract_usage` has no other source for `duration_s`.
        body["_elapsed_s"] = time.monotonic() - started
        return body

    @staticmethod
    def _as_openai_message(message: dict[str, Any]) -> dict[str, Any]:
        """Translate this service's neutral message shape onto the OpenAI content-block form.

        Only images need translating: agents build Ollama's `{"images": [b64, ...]}` (see
        `UIUXAgent`), while this API takes typed content blocks. Everything else passes
        through untouched, including `tool_calls` on an assistant turn being re-sent.
        """
        images = message.get("images")
        if not images:
            return message

        blocks: list[dict[str, Any]] = []
        if message.get("content"):
            blocks.append({"type": "text", "text": message["content"]})
        for image in images:
            # Already-formed URLs pass through; bare base64 gets the data-URI wrapper this
            # API requires. JPEG is the safe default for a screenshot that arrived without
            # a declared type.
            url = image if str(image).startswith(("http://", "https://", "data:")) else (
                f"data:image/jpeg;base64,{image}"
            )
            blocks.append({"type": "image_url", "image_url": {"url": url}})

        translated = {k: v for k, v in message.items() if k not in ("images", "content")}
        translated["content"] = blocks
        return translated

    @staticmethod
    def _as_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Wrap `ToolRegistry.schema()`'s neutral entry in the function envelope.

        Identical in shape to Ollama's, but duplicated rather than shared: the registry stays
        backend-agnostic by design (M2.1), and two backends agreeing today is not a reason to
        couple them.
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

    def _message(self, raw: dict[str, Any]) -> dict[str, Any]:
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(f"Unexpected response shape from backend: {raw!r:.300}")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderError(f"Unexpected response shape from backend: {raw!r:.300}")
        return message

    def extract_content(self, raw: dict[str, Any]) -> str:
        message = self._message(raw)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            # An empty body with tool calls present is a normal tool-calling turn, not an
            # error — the same trap as Ollama's native path (CLAUDE.md §5: never resolve a
            # tool call through extract_content).
            if message.get("tool_calls"):
                raise ProviderError(
                    "Model returned tool calls and no text; use extract_tool_calls"
                )
            raise ProviderError("Model returned an empty response")

        cleaned = strip_thinking(content)
        if not cleaned:
            raise ProviderError("Model returned reasoning only, with no answer")
        return cleaned

    def extract_tool_calls(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        message = self._message(raw)
        calls = []
        for entry in message.get("tool_calls") or []:
            function = entry.get("function") if isinstance(entry, dict) else None
            if not isinstance(function, dict):
                continue
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                # The normal case on this API — arguments arrive as a JSON string, where
                # Ollama sends a dict. Malformed JSON becomes an empty dict so M2.2's
                # validation reports it as a bad call, rather than crashing the provider.
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            calls.append({"name": function.get("name"), "arguments": arguments})
        return calls

    def extract_assistant_message(self, raw: dict[str, Any]) -> dict[str, Any]:
        message = self._message(raw)
        assistant: dict[str, Any] = {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),  # UNSTRIPPED — see the base-class docstring
        }
        # Servers with a reasoning parser (vLLM, SGLang) split thinking out here instead of
        # leaving it inline. Carry it, or `preserve_thinking` has nothing to preserve.
        if message.get("reasoning_content"):
            assistant["reasoning_content"] = message["reasoning_content"]
        if message.get("tool_calls"):
            assistant["tool_calls"] = message["tool_calls"]
        return assistant

    def extract_usage(self, raw: dict[str, Any]) -> RunUsage:
        usage = raw.get("usage") or {}
        return RunUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            response_tokens=usage.get("completion_tokens", 0),
            duration_s=raw.get("_elapsed_s", 0.0),
        )

    async def health(self) -> bool:
        try:
            response = await self._client.get("/v1/models", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
