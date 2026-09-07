"""Unit tests for the M4.1 token budgeter. Pure functions, no model calls."""

import math

from app.core.model_profile import ModelProfile
from app.core.token_budget import (
    count_tokens,
    effective_context_window,
    max_text_bytes,
    plan_budget,
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


def test_max_text_bytes_round_trips_under_count_tokens():
    # Text trimmed to this many bytes must count back at or under the token allowance —
    # otherwise M2.3's truncation would hand back a result that overflows its own budget.
    for tokens in (1, 10, 500, 4096):
        budget_bytes = max_text_bytes(tokens)
        assert count_tokens("a" * budget_bytes) <= tokens


def test_max_text_bytes_is_zero_for_no_allowance():
    assert max_text_bytes(0) == 0
    assert max_text_bytes(-50) == 0


def test_effective_context_window_defaults_to_the_full_profile_window():
    # None (the default) means "use the whole window this model has" — the point of making
    # MODEL_NUM_CTX optional, so a bigger model widens the budget with no second setting.
    assert effective_context_window(_SMALL_PROFILE, None) == 32_768
    assert effective_context_window(_LARGE_PROFILE, None) == 262_144


def test_effective_context_window_lets_config_constrain_but_not_inflate():
    assert effective_context_window(_LARGE_PROFILE, 4096) == 4096
    assert effective_context_window(_SMALL_PROFILE, 100_000) == 32_768


def test_plan_budget_subtracts_measured_costs_from_the_window():
    budget = plan_budget(
        profile=_SMALL_PROFILE,
        configured_num_ctx=None,
        reserved_output=1500,
        system="a" * 400,  # 115 tokens
        tool_schema="b" * 400,  # 115 tokens
        current_input="c" * 400,  # 115 tokens
    )
    assert budget.total == 32_768
    assert budget.fixed == budget.system + budget.tool_schema + budget.current_input
    assert budget.available == budget.total - budget.reserved_output - budget.fixed
    assert budget.is_over_budget is False


def test_plan_budget_fixed_cost_does_not_scale_with_the_window():
    """The bug the fraction model had: `system` and `tool_schema` cost what they cost.

    A percentage-based split handed them a share of the window, so the same 473-token real
    need was allocated ~52k tokens on a 262k window. Measured costs must be identical
    across windows; only `available` grows.
    """
    kwargs = dict(
        reserved_output=1500,
        system="a" * 400,
        tool_schema="b" * 400,
        current_input="c" * 400,
    )
    small = plan_budget(profile=_SMALL_PROFILE, configured_num_ctx=None, **kwargs)
    large = plan_budget(profile=_LARGE_PROFILE, configured_num_ctx=None, **kwargs)

    assert small.fixed == large.fixed
    assert small.reserved_output == large.reserved_output
    # All of the extra window flows into the one pool that can actually use it.
    assert large.available - small.available == large.total - small.total


def test_plan_budget_reports_over_budget_instead_of_hiding_it():
    # Fixed cost + reservation exceed a tiny window. The fraction model could not express
    # this state at all — it always returned a full-looking allocation.
    tiny = ModelProfile(
        name="test-tiny",
        context_window=512,
        supports_vision=False,
        supports_native_tools=False,
        tool_call_style="prompt",
        reliability_tier="small",
    )
    budget = plan_budget(
        profile=tiny,
        configured_num_ctx=None,
        reserved_output=400,
        system="a" * 1000,
        current_input="c" * 1000,
    )
    assert budget.available < 0
    assert budget.is_over_budget is True


def test_plan_budget_to_dict_has_every_field():
    budget = plan_budget(
        profile=_SMALL_PROFILE,
        configured_num_ctx=None,
        reserved_output=1500,
        system="hello",
    )
    assert budget.to_dict() == {
        "total": budget.total,
        "reserved_output": budget.reserved_output,
        "system": budget.system,
        "tool_schema": budget.tool_schema,
        "current_input": budget.current_input,
        "fixed": budget.fixed,
        "available": budget.available,
    }
