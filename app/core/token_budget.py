"""Owns the model's context window: counts tokens, and plans per call how much of the
window is already spoken for and how much is left.

**Measured, not apportioned.** An earlier version of this module split the window into
fixed fractions (system 10%, history 30%, ...). That was wrong in a way that got *worse*
as the window grew: `system` and `tool_schema` cost what they cost — measured at 53 and
420 tokens for `ui_ux` — whether the window is 4k or 1M. A percentage handed those two
52,428 tokens on a 262k window, and ~209k on a YaRN-extended 1M one, for a real need of
473. Fractions are only defensible for things that do not exist yet and therefore cannot
be measured.

So the segments split by **when they can be known**, and get opposite treatment:

- **Measurable before the call** — `system`, `tool_schema`, `current_input`: counted and
  subtracted. Never allocated a share.
- **Does not exist yet** — `reserved_output`: genuinely reserved, as a *floor*. It is what
  stops the window being filled so full there is no room left to answer. On a large window
  it never binds; on a small one it is the only thing preventing an overflow.

What remains is `available`: one shared pool the elastic segments draw from — history, tool
results, and later M6.4's retrieved context and M3.2's skills. They need no pre-split,
because M4.3 already defines the order they are sacrificed in (drop oldest tool results →
drop oldest turns → summarize → trim retrieved context). That order *is* the policy; a
second, fraction-based one would only contradict it.

`available < 0` is a real and reportable state, not an impossible one: it says the fixed
cost plus the output reservation already exceed the window. The fraction model could not
express that at all — it always returned a full-looking allocation.

**No number here is tied to a model.** The dev/prod difference is entirely
`ModelProfile.context_window` plus the per-domain `reserved_output`; see ROADMAP M4.1.
"""

import logging
import math
from dataclasses import dataclass

from app.core.model_profile import ModelProfile

logger = logging.getLogger(__name__)

# No tokenizer is bundled (Python 3.10, no new dependency — same call made for fetch_docs's
# stdlib HTML parsing) and Ollama exposes no tokenize-only endpoint: extract_usage's
# prompt_eval_count only exists after a call completes, too late for a pre-send budget.
#
# Counted in UTF-8 BYTES, not `len(str)` codepoints: BPE tokenizers (Qwen included) operate
# on UTF-8 bytes, so a Vietnamese or CJK character — 1 codepoint but 2-4 bytes — costs more
# tokens than an ASCII character at the same codepoint count. A codepoint-based chars/4
# heuristic systematically undercounts non-ASCII text; counting bytes tracks the real cost
# much closer, with no new dependency. 4 bytes/token is the standard rough estimate; the 15%
# margin biases toward overestimating on top of that, since a count that is too low is the
# one that actually overflows the window.
_BYTES_PER_TOKEN = 4
_SAFETY_MARGIN = 1.15


@dataclass(frozen=True)
class TokenBudget:
    """One call's plan. Every field is a token count."""

    total: int  # the effective window this call may use
    reserved_output: int  # floor kept free for the response (see module docstring)

    # Measured, incompressible. Their sum is `fixed`.
    system: int
    tool_schema: int
    current_input: int
    fixed: int

    # window - reserved_output - fixed. Shared by history, tool results, and later
    # retrieved context and skills. Negative means the call does not fit as composed.
    available: int

    @property
    def is_over_budget(self) -> bool:
        return self.available < 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "reserved_output": self.reserved_output,
            "system": self.system,
            "tool_schema": self.tool_schema,
            "current_input": self.current_input,
            "fixed": self.fixed,
            "available": self.available,
        }


def count_tokens(text: str) -> int:
    """Approximate token count for text not yet sent to the model. See the module docstring
    for why this counts UTF-8 bytes (not `len(str)` codepoints) with a safety margin, rather
    than a real tokenizer."""
    if not text:
        return 0
    return math.ceil(len(text.encode("utf-8")) / _BYTES_PER_TOKEN * _SAFETY_MARGIN)


def max_text_bytes(tokens: int) -> int:
    """Inverse of `count_tokens`: the largest UTF-8 byte length that still fits `tokens`.

    Used to turn a token allowance back into a truncation limit for a string (M2.3's tool
    result cap). Deliberately the exact inverse, margin included, so a string trimmed to
    this length counts back at or under `tokens`.
    """
    if tokens <= 0:
        return 0
    return int(tokens * _BYTES_PER_TOKEN / _SAFETY_MARGIN)


def effective_context_window(profile: ModelProfile, configured_num_ctx: int | None) -> int:
    """The window actually in effect.

    `configured_num_ctx` (`Settings.model_num_ctx`) is what `OllamaProvider` sends as
    `options.num_ctx`. It is **optional on purpose**: unset means "use the whole window the
    profile describes", so pointing `MODEL_NAME` at a bigger model widens the budget with no
    second setting to remember. Set it only to *constrain* a run below the model's real
    capability — a local CPU box short on RAM — never to describe the model, which is
    `ModelProfile`'s job.
    """
    if configured_num_ctx is None:
        return profile.context_window
    return min(profile.context_window, configured_num_ctx)


def plan_budget(
    *,
    profile: ModelProfile,
    configured_num_ctx: int | None,
    reserved_output: int,
    system: str = "",
    tool_schema: str = "",
    current_input: str = "",
) -> TokenBudget:
    """Plan one call: measure what is already spoken for, reserve room to answer, report
    what is left.

    Must be re-run before **every** model call, not once per run — M5.2's loop grows the
    tool-result tail on each iteration, so a budget planned at run start is stale by the
    second call.

    `tool_schema` is the serialized schema handed to the backend (`json.dumps` of
    `ToolRegistry.schema()`). Its token cost is an estimate of an estimate — Ollama renders
    the schema into the model's chat template, so the exact on-wire cost differs — but it is
    real context, and counting it approximately beats the previous behaviour of counting it
    not at all.
    """
    total = effective_context_window(profile, configured_num_ctx)

    system_tokens = count_tokens(system)
    tool_schema_tokens = count_tokens(tool_schema)
    current_input_tokens = count_tokens(current_input)
    fixed = system_tokens + tool_schema_tokens + current_input_tokens
    available = total - reserved_output - fixed

    budget = TokenBudget(
        total=total,
        reserved_output=reserved_output,
        system=system_tokens,
        tool_schema=tool_schema_tokens,
        current_input=current_input_tokens,
        fixed=fixed,
        available=available,
    )

    if budget.is_over_budget:
        # Not an exception: trimming history or tool results (M4.3) can still rescue this
        # call, and raising here would 500 a request that is merely tight. But it must be
        # loud — it means the fixed cost alone cannot be served by this window.
        logger.warning(
            "token budget exceeded before any history: window=%d reserved_output=%d "
            "fixed=%d (system=%d tool_schema=%d current_input=%d) available=%d",
            total,
            reserved_output,
            fixed,
            system_tokens,
            tool_schema_tokens,
            current_input_tokens,
            available,
        )
    return budget
