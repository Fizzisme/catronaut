"""Per-model capability profiles.

The dev/prod split (`qwen3:4b` vs `qwen3.8-27b`) is not just a config value — the two models
differ in context window, vision, and tool-calling reliability. Without this abstraction that
difference leaks into scattered `if model_name == "qwen3:4b"` checks across agents and the loop.
`ModelProfile` is the single place that difference is described; everything else reads it.
"""

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

ToolCallStyle = Literal["native", "prompt", "none"]
ReliabilityTier = Literal["small", "large"]


@dataclass(frozen=True)
class ModelProfile:
    name: str
    context_window: int
    supports_vision: bool
    supports_native_tools: bool
    tool_call_style: ToolCallStyle
    reliability_tier: ReliabilityTier

    # Output tokens this model spends *thinking* before it starts answering, to be held free
    # on top of whatever the domain reserves for the answer itself (see
    # `Agent.reserved_output_tokens`). Reasoning is output: it consumes the same budget as the
    # response, and running out mid-reasoning yields an empty answer, not a short one.
    #
    # Deliberately **no default**: a new profile silently inheriting 0 would under-reserve on a
    # thinking model, and the failure is invisible until an answer comes back truncated. Same
    # reasoning as `Tool.read_only`.
    reasoning_reserve_tokens: int

    # True when a conversation turn sent back to this model is expected to still carry its
    # `<think>` block. `qwen3.8-27b` enables `preserve_thinking` by default, retaining thinking
    # from *all* prior messages for decision consistency and KV-cache reuse
    # (docs/qwen3.8-27b-reference.md); `qwen3:4b` has no such feature.
    #
    # Two consequences for whoever builds the message list (M4.2), which is why this is a
    # profile field and not a provider detail:
    #   1. A history turn costs MORE than its visible text. Budget it by what actually goes on
    #      the wire — see `ModelProvider.extract_assistant_message`, not `extract_content`.
    #   2. Dropping thinking to save budget is a real trade with a stated cost, not free
    #      cleanup. Whether to drop it is policy (M5.3); this field only states what the model
    #      expects.
    retains_thinking_in_history: bool


# Keyed by exact Ollama tag. Add an entry here whenever a new model is put behind MODEL_NAME —
# do not branch on model_name anywhere else in the codebase.
_PROFILES: dict[str, ModelProfile] = {
    # Native tool calling MEASURED on 2026-08-31, not assumed: Ollama reports
    # capabilities ['completion', 'tools', 'thinking'] for this tag, and a real call
    # returned a well-formed `message.tool_calls` (37.3s, 510 tokens) with the tool call
    # kept out of `content` entirely. See ROADMAP M2.2. The earlier `False`/`"prompt"`
    # here was a guess made before the field had a consumer — do not restore it from
    # memory of the old CLAUDE.md wording.
    "qwen3:4b": ModelProfile(
        name="qwen3:4b",
        context_window=32_768,
        supports_vision=False,
        supports_native_tools=True,
        tool_call_style="native",
        # MEASURED (CLAUDE.md §3): this tag ignores `think: false` and reasons anyway —
        # 646 tokens for reasoning + answer on one prompt, and 900 tokens of pure reasoning
        # when `think: true`. 1024 covers the observed spread with room to spare.
        reasoning_reserve_tokens=1_024,
        # No preserve_thinking feature on this tag; it leaks a bare closing tag instead.
        retains_thinking_in_history=False,
        reliability_tier="small",
    ),
    # NOT measured — same family as the 4B and almost certainly also tool-capable, but
    # nothing has verified it. Left on the prompt path deliberately: the conservative
    # setting works on every model, so an unverified profile degrades rather than breaks.
    "qwen3:8b": ModelProfile(
        name="qwen3:8b",
        context_window=32_768,
        supports_vision=False,
        supports_native_tools=False,
        tool_call_style="prompt",
        # Same family as the 4B and never measured either; inherit the 4B's figure rather
        # than invent a bigger one for a model nobody has run.
        reasoning_reserve_tokens=1_024,
        retains_thinking_in_history=False,
        reliability_tier="small",
    ),
    # Prod target (decided 2026-08-29). NOT a Qwen3 variant — Qwen3.8 is a newer generation
    # built on Qwen3.5's architecture, so do not reason about it by analogy with `qwen3:4b`.
    #
    # Every field below is CONFIRMED against the official model card, kept at
    # docs/qwen3.8-27b-reference.md (verified 2026-09-08):
    #   context_window        262,144 native ("extensible to 1,000,000" via YaRN — raise this
    #                         number only when YaRN is actually configured on the server, since
    #                         the budgeter now treats it as the real window)
    #   supports_vision       native vision-language: images AND video
    #   supports_native_tools benchmarked through agentic tool-calling harnesses
    #   tool_call_style       serves an OpenAI-compatible Chat Completions API
    #
    # Still not in the public Ollama library (checked 2026-08-29) — and the card recommends
    # vLLM / SGLang / TokenSpeed, not Ollama, so prod likely needs a second ModelProvider
    # rather than a Modelfile. See ROADMAP M1.6.
    "qwen3.8-27b": ModelProfile(
        name="qwen3.8-27b",
        context_window=262_144,
        supports_vision=True,
        supports_native_tools=True,
        tool_call_style="native",
        # Thinking is ON by default here with `reasoning_effort` defaulting to `xhigh`, and
        # the card allows reasoning content up to 262,144 tokens — a ceiling, not a typical
        # spend. 32,768 is taken from the card's own agentic evaluations, which run this model
        # at `max_tokens=32,768`; it is 12.5% of the native window, which the 262k context can
        # absorb easily. Revisit against real traces once M1.6 can actually reach the model —
        # this is the one field here NOT confirmed by a card figure, but derived from one.
        reasoning_reserve_tokens=32_768,
        # `preserve_thinking` is enabled by default for all workloads on this model.
        retains_thinking_in_history=True,
        reliability_tier="large",
    ),
}

# Used for any model_name with no explicit entry above, so the service degrades safely
# (small context, no vision, no native tools) instead of guessing capabilities it can't verify.
_DEFAULT_PROFILE = ModelProfile(
    name="unknown",
    context_window=4_096,
    supports_vision=False,
    supports_native_tools=False,
    tool_call_style="prompt",
    # Assume it reasons — most current open models do, and reserving room a model turns out
    # not to need costs only a little context, while reserving none for a model that does
    # need it truncates the answer.
    reasoning_reserve_tokens=1_024,
    # Conservative: assume history does NOT need to carry thinking. Wrong in the cheap
    # direction — the model loses reasoning continuity, rather than the budget silently
    # undercounting every turn.
    retains_thinking_in_history=False,
    reliability_tier="small",
)


def get_model_profile(model_name: str) -> ModelProfile:
    profile = _PROFILES.get(model_name)
    if profile is None:
        logger.warning(
            "No ModelProfile for model_name=%r; falling back to conservative defaults "
            "(no vision, no native tools, %d-token context). Add an entry to "
            "app/core/model_profile.py if this model is expected to be used.",
            model_name,
            _DEFAULT_PROFILE.context_window,
        )
        return _DEFAULT_PROFILE
    return profile
