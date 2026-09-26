from evals.spikes.m0_2.common import make_prompt, median, server_root
from evals.spikes.m0_2.tool_calls import TOOLS, build_cases


def test_server_root_strips_v1() -> None:
    assert server_root("http://gpu:8000/v1") == "http://gpu:8000"
    assert server_root("http://gpu:8000/v1/") == "http://gpu:8000"


def test_make_prompt_is_unique_and_scales() -> None:
    assert make_prompt(2_000) != make_prompt(2_000)  # random tag defeats prefix-cache reuse
    assert len(make_prompt(8_000)) > len(make_prompt(2_000))


def test_median_of_empty_is_nan() -> None:
    assert median([1.0, 3.0, 2.0]) == 2.0
    assert median([]) != median([])  # NaN is the only value not equal to itself


def test_tool_call_cases_cover_every_tool() -> None:
    cases = build_cases()
    assert len(cases) == 50
    tool_names = {tool["function"]["name"] for tool in TOOLS}
    assert {case.tool for case in cases} == tool_names
