"""Owns the model's context window: counts tokens and splits the effective window into
fixed slots (system, retrieved context, history, tool results, reserved output).

Nothing consumes the slot values yet — M4.2's assembly pipeline and M4.3's truncation
strategy are the first callers, and M6.4 (RAG injection) blocks on this existing. See
ROADMAP M4.1. `RunContext.token_budget` is populated eagerly by `Agent._new_run_context`
so those milestones have something to read from day one.
"""

import math
from dataclasses import dataclass

from app.core.model_profile import ModelProfile

# No tokenizer is bundled (Python 3.10, no new dependency — same call made for fetch_docs's
# stdlib HTML parsing) and Ollama exposes no tokenize-only endpoint: extract_usage's
# prompt_eval_count only exists after a call completes, too late for a pre-send budget.
# chars/4 is the standard rough estimate for English/code text; the 15% margin biases toward
# overestimating, since a count that's too low is the one that actually overflows the window.
_CHARS_PER_TOKEN = 4
_SAFETY_MARGIN = 1.15

# Fractions of the effective window (see effective_context_window) — must sum to 1.0.
# Reserved output gets the largest single share on purpose: CLAUDE.md's measured behaviour
# on qwen3:4b is that it always reasons regardless of `think`, and a tight num_predict
# truncates mid-reasoning into an empty answer (observed) rather than a short one.
_RESERVED_OUTPUT_FRACTION = 0.30
_HISTORY_FRACTION = 0.30
_SYSTEM_FRACTION = 0.10
_RETRIEVED_CONTEXT_FRACTION = 0.15
_TOOL_RESULTS_FRACTION = 0.15


@dataclass(frozen=True)
class TokenBudget:
    total: int
    system: int
    retrieved_context: int
    history: int
    tool_results: int
    reserved_output: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "system": self.system,
            "retrieved_context": self.retrieved_context,
            "history": self.history,
            "tool_results": self.tool_results,
            "reserved_output": self.reserved_output,
        }


def count_tokens(text: str) -> int:
    """Approximate token count for text not yet sent to the model. See the module
    docstring for why this is chars/4 with a safety margin rather than a real tokenizer."""
    if not text:
        return 0
    return math.ceil(len(text) / _CHARS_PER_TOKEN * _SAFETY_MARGIN)


def effective_context_window(profile: ModelProfile, configured_num_ctx: int) -> int:
    """The window actually in effect, not just the profile's ceiling.

    `configured_num_ctx` (Settings.model_num_ctx) is what OllamaProvider actually sends as
    `options.num_ctx` — it defaults to 4096 in dev, well under qwen3:4b's 32768-token profile
    ceiling. Budgeting off the profile alone would allocate slots the model was never actually
    given. lifespan.py already warns the other direction (num_ctx exceeding the profile); this
    is the same guard applied to the budgeter.
    """
    return min(profile.context_window, configured_num_ctx)


def allocate_budget(profile: ModelProfile, configured_num_ctx: int) -> TokenBudget:
    """Split the effective window into fixed slots. Deterministic and profile-driven — the
    dev/prod difference is `configured_num_ctx` and `profile.context_window`, not a branch on
    model name (see app/core/model_profile.py)."""
    total = effective_context_window(profile, configured_num_ctx)
    return TokenBudget(
        total=total,
        system=math.floor(total * _SYSTEM_FRACTION),
        retrieved_context=math.floor(total * _RETRIEVED_CONTEXT_FRACTION),
        history=math.floor(total * _HISTORY_FRACTION),
        tool_results=math.floor(total * _TOOL_RESULTS_FRACTION),
        reserved_output=math.floor(total * _RESERVED_OUTPUT_FRACTION),
    )
