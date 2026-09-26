"""M0.3 — run every preview fixture through Sandpack and record what happens.

Build the harness first (evals/spikes/m0_3/harness: npm ci && npm run build), then:
    uv run python -m evals.spikes.m0_3.run_fixtures                        # CodeSandbox-hosted bundler
    uv run python -m evals.spikes.m0_3.run_fixtures --bundler-dir PATH     # self-hosted bundler files

Per fixture: bundle time on a cold and a warm load, bundler and runtime errors, external hosts
contacted, starter navigation checks, and two screenshots (Playwright and the in-iframe bridge).
"""

import argparse
import base64
import functools
import http.server
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from playwright.sync_api import BrowserContext, Frame, Page, sync_playwright

HERE = Path(__file__).parent
DIST = HERE / "harness" / "dist"
FIXTURES = HERE / "fixtures"
TIMEOUT_S = 180
SETTLE_S = 3


@dataclass
class Load:
    status: str
    timings: dict[str, int]
    errors: list[dict[str, Any]]
    renders: list[dict[str, Any]]
    notes: list[str]


@dataclass
class Result:
    fixture: str
    bundler: str
    expect: dict[str, str]
    cold: Load | None = None
    warm: Load | None = None
    checks: dict[str, bool] = field(default_factory=dict[str, bool])
    hosts: list[str] = field(default_factory=list[str])
    probe_after_render_ms: int | None = None  # deps/*: probe element visible, after first render
    screenshot_ms: float | None = None
    screenshot_error: str | None = None
    passed: bool = False


def fixture_names() -> list[tuple[str, dict[str, str]]]:
    names: list[tuple[str, dict[str, str]]] = [
        ("starter", {"status": "rendered", "errorIncludes": ""})
    ]
    for manifest in sorted(FIXTURES.rglob("fixture.json")):
        name = manifest.parent.relative_to(FIXTURES).as_posix()
        names.append((name, json.loads(manifest.read_text(encoding="utf-8"))["expect"]))
    return names


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def load_once(page: Page, url: str) -> Load:
    page.goto(url)
    deadline = time.monotonic() + TIMEOUT_S
    status = "loading"
    while time.monotonic() < deadline:
        status = page.evaluate("window.__preview ? window.__preview.state.status : 'loading'")
        if status in ("rendered", "failed"):
            break
        time.sleep(0.25)
    time.sleep(SETTLE_S)  # late runtime errors (effects, rejected promises) arrive after the render
    state: dict[str, Any] = page.evaluate("window.__preview.state")
    return Load(
        status=state["status"] if status in ("rendered", "failed") else "timeout",
        timings=state["timings"],
        errors=state["errors"],
        renders=state["renders"],
        notes=state["notes"],
    )


def preview_frame(page: Page) -> Frame:
    handle = page.locator("#preview").element_handle()
    frame = handle.content_frame() if handle else None
    if frame is None:
        raise RuntimeError("preview iframe has no frame")
    return frame


def heading(frame: Frame) -> str:
    try:
        return frame.locator("[data-testid=heading]").first.inner_text(timeout=5000).strip()
    except Exception:
        return ""


def wait_heading(frame: Frame, expected: str) -> bool:
    for _ in range(20):
        if expected in heading(frame):
            return True
        time.sleep(0.25)
    return False


def check_starter(frame: Frame) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    checks["home heading"] = wait_heading(frame, "Make it")
    checks["home title from metadata"] = frame.evaluate("document.title") == "Starter"
    checks["tailwind theme colour applied"] = (
        frame.evaluate("getComputedStyle(document.querySelector('header a')).color")
        == "rgb(255, 90, 31)"
    )
    checks["next/font variable applied"] = "Playfair" in frame.evaluate(
        "getComputedStyle(document.querySelector('[data-testid=heading]')).fontFamily"
    )
    checks["next/image fill"] = (
        frame.evaluate("getComputedStyle(document.querySelector('img')).position") == "absolute"
    )
    frame.locator("[data-testid=counter]").click()
    checks["client state"] = "Clicked 1" in frame.locator("[data-testid=counter]").inner_text()

    frame.locator("header a[href='/about']").click()
    checks["Link -> /about"] = wait_heading(frame, "About us")
    checks["pathname /about"] = frame.evaluate("location.pathname") == "/about"
    checks["title template"] = frame.evaluate("document.title") == "About | Starter"

    frame.locator("header a[href='/blog']").click()
    wait_heading(frame, "Hello")
    frame.locator("a[href='/blog/hello-world']").click()
    checks["[slug] params via use()"] = wait_heading(frame, "Hello, world") and (
        frame.locator("[data-testid=slug]").inner_text() == "hello-world"
    )

    frame.locator("header a[href='/pricing']").click()
    checks["route group (marketing)"] = wait_heading(frame, "Pricing")
    checks["group layout wraps page"] = frame.locator("[data-testid=marketing-layout]").count() == 1

    frame.evaluate("history.back()")
    checks["history back"] = wait_heading(frame, "Hello, world")

    frame.evaluate("window.__catronautRouter.navigate('/blog/missing-post')")
    checks["notFound() -> not-found.tsx"] = wait_heading(frame, "Page not found")
    frame.evaluate("window.__catronautRouter.navigate('/no/such/route')")
    checks["unknown route -> not-found.tsx"] = wait_heading(frame, "Page not found")

    frame.evaluate("window.__catronautRouter.navigate('/')")
    wait_heading(frame, "Make it")
    frame.locator("[data-testid=push]").click()
    checks["router.push + useSearchParams"] = (
        wait_heading(frame, "About us") and frame.evaluate("location.search") == "?from=home"
    )
    return checks


def check_async_page(frame: Frame) -> dict[str, bool]:
    frame.evaluate("window.__catronautRouter.navigate('/blog/hello-world')")
    ok = wait_heading(frame, "Hello, world")
    return {"async page with await params": ok}


def check_async_component(frame: Frame) -> dict[str, bool]:
    frame.evaluate("window.__catronautRouter.navigate('/about')")
    wait_heading(frame, "About us")
    return {"nested async component renders": wait_heading(frame, "Ada")}


def check_dependency(frame: Frame, selector: str, result: Result) -> dict[str, bool]:
    # lazy chunks (next/dynamic) are fetched and transpiled after the first render: wait for them
    started = time.monotonic()
    try:
        frame.locator(selector).first.wait_for(timeout=30_000)
        found = True
        result.probe_after_render_ms = round((time.monotonic() - started) * 1000)
    except Exception:
        found = False
    return {"heading visible": heading(frame) != "", f"{selector} rendered": found}


def evaluate(result: Result) -> bool:
    cold = result.cold
    if cold is None:
        return False
    expect = result.expect
    messages = " | ".join(
        f"{e.get('kind')}: {e.get('message')} {e.get('path', '')}" for e in cold.errors
    )
    status_ok = expect["status"] == "any" or cold.status == expect["status"]
    if expect["errorIncludes"]:
        errors_ok = expect["errorIncludes"] in messages
    elif expect["status"] == "rendered":  # a clean render: no bundler or runtime error at all
        errors_ok = not [e for e in cold.errors if e.get("source") in ("bundler", "runtime")]
    else:
        errors_ok = True
    return status_ok and errors_ok and all(result.checks.values())


def run_fixture(context: BrowserContext, base: str, bundler: str, name: str, out: Path) -> Result:
    result = Result(fixture=name, bundler=bundler or "hosted", expect={})
    hosts: set[str] = set()
    context.on("request", lambda request: hosts.add(urlparse(request.url).netloc))
    page = context.new_page()
    url = f"{base}/?fixture={quote(name)}&bundler={quote(bundler)}"
    result.cold = load_once(page, url)
    shot_name = name.replace("/", "__")
    if result.cold.status == "rendered":
        frame = preview_frame(page)
        if name == "starter":
            result.checks = check_starter(frame)
            frame.evaluate("window.__catronautRouter.navigate('/')")
            wait_heading(frame, "Make it")
        elif name == "errors/async-page":
            result.checks = check_async_page(frame)
        elif name == "errors/async-component":
            result.checks = check_async_component(frame)
        elif name == "deps/three-r3f":
            result.checks = check_dependency(frame, "canvas", result)
        elif name.startswith("deps/"):
            result.checks = check_dependency(frame, "[data-testid=probe]", result)
        time.sleep(SETTLE_S)
        # errors raised while the checks navigated count too
        result.cold.errors = page.evaluate("window.__preview.state.errors")
        page.locator("#preview").screenshot(path=out / f"{shot_name}.playwright.png")
        shot: dict[str, Any] = page.evaluate("window.__preview.screenshot()")
        result.screenshot_ms = shot.get("ms")
        result.screenshot_error = shot.get("error")
        data_url = shot.get("dataUrl")
        if isinstance(data_url, str):
            png = base64.b64decode(data_url.split(",", 1)[1])
            (out / f"{shot_name}.bridge.png").write_bytes(png)
    else:
        page.locator("#preview").screenshot(path=out / f"{shot_name}.playwright.png")
    result.warm = load_once(page, url)
    page.close()
    result.hosts = sorted(h for h in hosts if h and not h.startswith("127.0.0.1"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--bundler-dir", type=Path, help="serve these bundler files (self-hosted)")
    parser.add_argument("--only", nargs="*", help="fixture names to run (default: all)")
    parser.add_argument("--out", type=Path, default=Path("m0_3_results"))
    args = parser.parse_args()

    if not (DIST / "index.html").exists():
        raise SystemExit(f"{DIST} is missing: run `npm ci && npm run build` in {DIST.parent}")
    label = "self" if args.bundler_dir else "hosted"
    out: Path = args.out / label
    out.mkdir(parents=True, exist_ok=True)

    harness_server, base = serve(DIST)
    bundler_server = None
    bundler = ""
    if args.bundler_dir:
        bundler_server, bundler = serve(args.bundler_dir)
        bundler += "/"

    results: list[Result] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, expect in fixture_names():
            if args.only and name not in args.only:
                continue
            # a fresh context per fixture: "cold" means an empty browser cache for that fixture
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            try:
                result = run_fixture(context, base, bundler, name, out)
            except Exception as error:  # a crashed fixture is a result too
                result = Result(fixture=name, bundler=label, expect=expect)
                result.checks = {f"harness crashed: {error}"[:200]: False}
            result.expect = expect
            result.passed = evaluate(result)
            results.append(result)
            context.close()
            cold = result.cold
            print(
                f"{'PASS' if result.passed else 'FAIL'}  {name:28} "
                f"cold={cold.status if cold else '-':9} "
                f"render={cold.timings.get('firstRender', '-') if cold else '-'}ms "
                f"warm={result.warm.timings.get('firstRender', '-') if result.warm else '-'}ms "
                f"errors={len(cold.errors) if cold else '-'}"
            )
        browser.close()

    harness_server.shutdown()
    if bundler_server:
        bundler_server.shutdown()
    (out / "results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8"
    )
    print(f"{sum(r.passed for r in results)}/{len(results)} passed -> {out / 'results.json'}")


if __name__ == "__main__":
    main()
