"""M0.2 — tool-call parse success over ~50 scripted calls.

Run: uv run python -m evals.spikes.m0_2.tool_calls --base-url http://HOST:8000/v1
"""

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast

from openai import AsyncOpenAI

from evals.spikes.m0_2.common import add_endpoint_args, make_client

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": "string"} for key in required},
                "required": required,
            },
        },
    }
    for name, description, required in [
        ("get_weather", "Get the current weather for a city.", ["city"]),
        ("read_file", "Read a text file from the workspace.", ["path"]),
        ("write_file", "Write text content to a file in the workspace.", ["path", "content"]),
        ("search_docs", "Search the documentation for a query.", ["query"]),
        ("calculate", "Evaluate an arithmetic expression.", ["expression"]),
    ]
]


@dataclass(frozen=True)
class Case:
    prompt: str
    tool: str
    required: tuple[str, ...]


def build_cases() -> list[Case]:
    cities = ["Hanoi", "Da Nang", "Hue", "Can Tho", "Hai Phong", "Nha Trang", "Da Lat", "Vinh",
              "Quy Nhon", "Vung Tau"]  # fmt: skip
    files = ["app/page.tsx", "app/layout.tsx", "components/Hero.tsx", "styles/globals.css",
             "package.json", "tailwind.config.ts", "app/about/page.tsx", "lib/utils.ts",
             "components/Nav.tsx", "README.md"]  # fmt: skip
    topics = ["next/image usage", "tailwind dark mode", "framer motion variants", "gsap scrolltrigger",
              "app router layouts", "react server components", "css grid areas", "font optimisation",
              "aria labels for buttons", "responsive images"]  # fmt: skip
    sums = ["12 * (7 + 5)", "1024 / 16", "3.5 * 4 - 2", "(100 - 37) * 2", "99 + 101 + 1",
            "2 ** 10", "81 / 9 + 4", "15 * 15", "1000 - 250 * 2", "(8 + 2) * (6 - 1)"]  # fmt: skip
    cases: list[Case] = []
    cases += [
        Case(f"What is the weather like in {c} right now?", "get_weather", ("city",))
        for c in cities
    ]
    cases += [Case(f"Open {f} and show me what is inside.", "read_file", ("path",)) for f in files]
    cases += [
        Case(
            f"Create {f} containing a short placeholder comment.", "write_file", ("path", "content")
        )
        for f in files
    ]
    cases += [Case(f"Look up the docs about: {t}.", "search_docs", ("query",)) for t in topics]
    cases += [
        Case(f"Compute {s} using the calculator tool.", "calculate", ("expression",)) for s in sums
    ]
    return cases


@dataclass
class Outcome:
    truncated: bool = False  # finish_reason == "length": the call must never be executed
    called: bool = False
    right_tool: bool = False
    args_valid: bool = False  # arguments parse as JSON and contain every required key
    error: str = ""


async def run_case(client: AsyncOpenAI, model: str, case: Case, max_tokens: int) -> Outcome:
    out = Outcome()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": case.prompt}],
            tools=cast("Any", TOOLS),
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - a spike reports every failure, it does not hide them
        out.error = f"{type(exc).__name__}: {exc}"
        return out
    choice = response.choices[0]
    out.truncated = choice.finish_reason == "length"
    calls = choice.message.tool_calls or []
    out.called = bool(calls)
    if not calls:
        return out
    call = cast("Any", calls[0])
    out.right_tool = call.function.name == case.tool
    try:
        arguments = json.loads(call.function.arguments)
        out.args_valid = isinstance(arguments, dict) and all(
            key in cast("dict[str, Any]", arguments) for key in case.required
        )
    except json.JSONDecodeError:
        out.args_valid = False
    return out


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_endpoint_args(parser)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()

    client = make_client(args)
    cases = build_cases()
    gate = asyncio.Semaphore(args.concurrency)

    async def guarded(case: Case) -> Outcome:
        async with gate:
            return await run_case(client, args.model, case, args.max_tokens)

    outcomes = await asyncio.gather(*(guarded(c) for c in cases))
    total = len(outcomes)
    for label, count in [
        ("tool call returned", sum(o.called for o in outcomes)),
        ("correct tool", sum(o.right_tool for o in outcomes)),
        ("arguments valid (parse success)", sum(o.args_valid for o in outcomes)),
        ("truncated (finish_reason=length)", sum(o.truncated for o in outcomes)),
        ("request errors", sum(bool(o.error) for o in outcomes)),
    ]:
        print(f"{label:<36} {count:>3}/{total}  ({count / total:.0%})")
    for case, outcome in zip(cases, outcomes, strict=True):
        if outcome.error or not outcome.args_valid:
            print(f"  FAIL: {case.prompt!r} -> {outcome}")


if __name__ == "__main__":
    asyncio.run(main())
