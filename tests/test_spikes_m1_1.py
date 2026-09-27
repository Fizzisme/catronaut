import asyncio

import httpx2

from app.core.llm import LLMConfig
from evals.spikes.m1_1.live_check import Result, run_checks
from tests.test_llm_client import Server, call_fragment, chunk, sse

CONFIG = LLMConfig(base_url="http://vllm/v1", model="m", max_attempts=1)


def reasoning_reply() -> httpx2.Response:
    return sse(
        chunk({"reasoning_content": "x + x + 1 = 1.1"}),
        chunk({"content": "0.05"}, finish="stop"),
        chunk(usage={"prompt_tokens": 40, "completion_tokens": 9, "total_tokens": 49}),
    )


def tool_call_reply() -> httpx2.Response:
    return sse(
        chunk({"reasoning_content": "I should read it."}),
        chunk({"tool_calls": [call_fragment(0, "", id="call_1", name="read_file")]}),
        chunk({"tool_calls": [call_fragment(0, '{"path": "app/page.tsx"}')]}),
        chunk({}, finish="tool_calls"),
    )


def probe_reply(prompt_tokens: int) -> httpx2.Response:
    return sse(
        chunk({"content": "T"}, finish="length"),
        chunk(usage={"prompt_tokens": prompt_tokens, "completion_tokens": 1, "total_tokens": 1}),
    )


def truncated_reply() -> httpx2.Response:
    fragment = call_fragment(0, '{"path": "app/page.tsx", "content": "exp', "call_2", "write_file")
    return sse(chunk({"tool_calls": [fragment]}), chunk({}, finish="length"))


def run(server: Server) -> list[Result]:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(server))
    return asyncio.run(run_checks(CONFIG, http_client=client))


def test_all_checks_pass_on_the_expected_server_behaviour() -> None:
    server = Server(
        reasoning_reply(),
        tool_call_reply(),
        probe_reply(120),
        probe_reply(100),
        truncated_reply(),
    )
    results = run(server)
    assert [(r.name, r.ok) for r in results] == [
        ("reasoning", True),
        ("tool_call", True),
        ("round_trip", True),
        ("truncation", True),
    ], results
    with_reasoning, without = server.bodies[2]["messages"][1], server.bodies[3]["messages"][1]
    assert with_reasoning["reasoning_content"] == "I should read it."
    assert "reasoning_content" not in without
    assert server.bodies[4]["chat_template_kwargs"] == {"enable_thinking": False}


def test_a_failing_check_does_not_stop_the_others() -> None:
    server = Server(reasoning_reply(), httpx2.Response(400), truncated_reply())
    results = run(server)
    assert [(r.name, r.ok) for r in results] == [
        ("reasoning", True),
        ("tool_call", False),
        ("round_trip", False),
        ("truncation", True),
    ]
    assert "LLMRequestError" in results[1].detail
