"""Unit tests for the M4.1 token budgeter. Pure functions, no model calls."""

import math

from app.core.model_profile import ModelProfile
from app.core.token_budget import (
    allocate_budget,
    count_tokens,
    effective_context_window,
)

_SMALL_PROFILE = ModelProfile(
    name="test-small",
    context_window=32_768,
    supports_vision=False,
    supports_native_tools=True,
    tool_call_style="native",
    reliability_tier="small",
)

_LARGE_PROFILE = ModelProfile(
    name="test-large",
    context_window=262_144,
    supports_vision=True,
    supports_native_tools=True,
    tool_call_style="native",
    reliability_tier="large",
)


def test_count_tokens_empty_string_is_zero():
    assert count_tokens("") == 0


def test_count_tokens_scales_with_length_and_overestimates():
    # ASCII: 1 byte/char, so 400 chars = 400 bytes / 4 bytes-per-token = 100,
    # plus the 15% safety margin.
    assert count_tokens("a" * 400) == 115


def test_count_tokens_counts_utf8_bytes_not_codepoints():
    # Vietnamese diacritics are 1 codepoint but 2-3 bytes in UTF-8 — a codepoint-based
    # chars/4 heuristic would undercount this text relative to a byte-based one.
    text = "Xin chào các bạn, đây là một câu tiếng Việt có dấu"
    char_based_estimate = math.ceil(len(text) / 4 * 1.15)
    assert count_tokens(text) > char_based_estimate


def test_effective_context_window_uses_the_smaller_of_the_two():
    # Dev default: configured num_ctx (4096) is well under the profile's ceiling (32768).
    assert effective_context_window(_SMALL_PROFILE, 4096) == 4096
    # A configured num_ctx above the profile ceiling is clamped down, mirroring lifespan.py's
    # warning about the same mismatch in the other direction.
    assert effective_context_window(_SMALL_PROFILE, 100_000) == 32_768


def test_allocate_budget_slots_sum_to_the_effective_window():
    budget = allocate_budget(_SMALL_PROFILE, 4096)
    assert budget.total == 4096
    slots = (
        budget.system
        + budget.retrieved_context
        + budget.history
        + budget.tool_results
        + budget.reserved_output
    )
    # Flooring each fraction means the sum can land a few tokens under the total, never over.
    assert slots <= budget.total
    assert budget.total - slots < 10


def test_allocate_budget_reserved_output_is_the_largest_slot():
    # CLAUDE.md §3: qwen3:4b always reasons; a tight reserved-output slot truncates mid-reasoning
    # into an empty answer. Reserved output must not be squeezed by any other slot.
    budget = allocate_budget(_SMALL_PROFILE, 32_768)
    assert budget.reserved_output >= budget.system
    assert budget.reserved_output >= budget.retrieved_context
    assert budget.reserved_output >= budget.tool_results
    assert budget.reserved_output >= budget.history


def test_allocate_budget_scales_with_profile():
    small = allocate_budget(_SMALL_PROFILE, _SMALL_PROFILE.context_window)
    large = allocate_budget(_LARGE_PROFILE, _LARGE_PROFILE.context_window)
    assert large.total > small.total
    assert large.reserved_output > small.reserved_output


def test_allocate_budget_to_dict_has_all_slots():
    budget = allocate_budget(_SMALL_PROFILE, 4096)
    assert budget.to_dict() == {
        "total": budget.total,
        "system": budget.system,
        "retrieved_context": budget.retrieved_context,
        "history": budget.history,
        "tool_results": budget.tool_results,
        "reserved_output": budget.reserved_output,
    }
