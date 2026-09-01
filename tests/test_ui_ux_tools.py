"""Tests for the ui_ux domain's tool pack (ROADMAP M2.4).

check_contrast/lookup_heuristic/format_review are pure — tested directly. fetch_docs
makes a real network call in run(), so its network layer (httpx) is monkeypatched;
its SSRF guard (DNS resolution, address classification) is tested directly since that
logic never touches the network itself.
"""

import ipaddress
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.tools.executor import ToolExecutor
from app.core.tools.parsing import ToolCall
from app.core.tools.policy import ToolPolicy
from app.core.tools.registry import ToolRegistry
from app.core.model_profile import get_model_profile
from app.core.run_context import RunContext
from app.domains.ui_ux.tools import TOOLS
from app.domains.ui_ux.tools.accessibility import CheckContrast, ContrastArgs, wcag_contrast_ratio
from app.domains.ui_ux.tools.heuristics import LookupArgs, LookupHeuristic
from app.domains.ui_ux.tools.report import FormatReview, ReportArgs
from app.domains.ui_ux.tools.web import (
    DocFetchError,
    FetchDocs,
    FetchDocsArgs,
    _assert_fetchable_url,
    _extract_text,
)


@pytest.fixture
def run():
    return RunContext(domain="ui_ux", model_profile=get_model_profile("qwen3:4b"))


# --- registry-level: the whole pack together ---------------------------------

def test_the_pack_registers_without_duplicate_names():
    registry = ToolRegistry(TOOLS)
    assert len(registry) == 4
    assert {t.name for t in registry} == {
        "check_contrast", "lookup_heuristic", "format_review", "fetch_docs",
    }


def test_every_tool_declares_read_only():
    for tool in TOOLS:
        assert isinstance(tool.read_only, bool)


def test_schemas_stay_flat_no_nested_objects(): # 4B gap: flat args, ROADMAP M2.1
    registry = ToolRegistry(TOOLS)
    for schema in registry.schema():
        for prop in schema["parameters"].get("properties", {}).values():
            assert prop.get("type") != "object", schema["name"]


def test_every_tool_has_at_most_three_params():  # 4B gap cap, ROADMAP M2.1
    registry = ToolRegistry(TOOLS)
    for schema in registry.schema():
        assert len(schema["parameters"].get("properties", {})) <= 3, schema["name"]


# --- check_contrast ------------------------------------------------------------

def test_wcag_ratio_black_on_white_is_max_contrast():
    assert wcag_contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)


def test_wcag_ratio_identical_colors_is_one():
    assert wcag_contrast_ratio("#777777", "#777777") == pytest.approx(1.0, abs=0.01)


def test_wcag_ratio_accepts_shorthand_hex():
    assert wcag_contrast_ratio("#000", "#fff") == pytest.approx(21.0, abs=0.01)


def test_contrast_args_rejects_invalid_hex():
    with pytest.raises(ValidationError):
        ContrastArgs(foreground="red", background="#ffffff")


@pytest.mark.asyncio
async def test_check_contrast_reports_aa_fail_for_low_contrast_gray():
    result = await CheckContrast().run(ContrastArgs(foreground="#999999", background="#ffffff"))
    assert "FAIL" in result  # ~2.85:1, measured in the M2.2 probe — fails AA normal text


@pytest.mark.asyncio
async def test_check_contrast_reports_aaa_pass_for_black_on_white():
    result = await CheckContrast().run(ContrastArgs(foreground="#000000", background="#ffffff"))
    assert "AAA normal text: PASS" in result


# --- lookup_heuristic ------------------------------------------------------------

@pytest.mark.asyncio
async def test_lookup_heuristic_returns_text_for_a_known_topic():
    result = await LookupHeuristic().run(LookupArgs(topic="error_prevention"))
    assert "error prevention" in result.lower()


def test_lookup_heuristic_rejects_an_unknown_topic():
    with pytest.raises(ValidationError):
        LookupArgs(topic="not_a_real_heuristic")


# --- format_review ------------------------------------------------------------

@pytest.mark.asyncio
async def test_format_review_includes_all_sections_when_present():
    result = await FormatReview().run(
        ReportArgs(summary="Looks ok.", issues=["Low contrast button"], recommendations=["Darken text"])
    )
    assert "## Summary" in result
    assert "## Issues" in result
    assert "## Recommendations" in result
    assert "Low contrast button" in result


@pytest.mark.asyncio
async def test_format_review_omits_empty_sections():
    result = await FormatReview().run(ReportArgs(summary="All good."))
    assert "## Issues" not in result
    assert "## Recommendations" not in result


# --- fetch_docs: SSRF guard (no network) ---------------------------------------

def test_fetch_docs_rejects_non_http_scheme():
    with pytest.raises(ValidationError):
        FetchDocsArgs(url="ftp://example.com/file")


def test_assert_fetchable_url_blocks_loopback(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(DocFetchError, match="non-public"):
        _assert_fetchable_url("http://internal.example/")


def test_assert_fetchable_url_blocks_cloud_metadata_address(monkeypatch):
    # 169.254.169.254 — the AWS/GCP/Azure metadata endpoint. Link-local, so
    # ipaddress.is_link_local already covers it; asserted explicitly since this is
    # the concrete attack this guard exists to stop.
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [(None, None, None, None, ("169.254.169.254", 0))],
    )
    with pytest.raises(DocFetchError, match="non-public"):
        _assert_fetchable_url("http://metadata.internal/")


def test_assert_fetchable_url_blocks_private_range(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [(None, None, None, None, ("10.0.0.5", 0))],
    )
    with pytest.raises(DocFetchError, match="non-public"):
        _assert_fetchable_url("http://internal.corp/")


def test_assert_fetchable_url_allows_a_public_address(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))],  # example.com
    )
    _assert_fetchable_url("http://example.com/")  # must not raise


def test_assert_fetchable_url_raises_on_dns_failure(monkeypatch):
    import socket as socket_module

    def _fail(host, port):
        raise socket_module.gaierror("name resolution failed")

    monkeypatch.setattr("socket.getaddrinfo", _fail)
    with pytest.raises(DocFetchError, match="could not resolve"):
        _assert_fetchable_url("http://nonexistent.invalid/")


# --- fetch_docs: HTML extraction (no network) -----------------------------------

def test_extract_text_strips_tags_and_scripts():
    html = b"<html><head><style>.x{}</style></head><body><script>evil()</script><p>Hello <b>world</b></p></body></html>"
    text = _extract_text("text/html", html)
    assert "Hello" in text
    assert "world" in text
    assert "evil" not in text


def test_extract_text_passes_through_plain_text():
    assert _extract_text("text/plain", b"just text") == "just text"


# --- fetch_docs: run() with network mocked --------------------------------------

@pytest.mark.asyncio
async def test_fetch_docs_returns_extracted_text(run):
    fake_response = AsyncMock()
    fake_response.is_redirect = False
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html"}
    fake_response.content = b"<p>Some documentation text.</p>"

    with patch("app.domains.ui_ux.tools.web._assert_fetchable_url"), \
         patch("httpx.AsyncClient.get", return_value=fake_response):
        result = await FetchDocs().run(FetchDocsArgs(url="http://example.com/docs"))

    assert "Some documentation text." in result


@pytest.mark.asyncio
async def test_fetch_docs_refuses_to_follow_a_redirect(run):
    fake_response = AsyncMock()
    fake_response.is_redirect = True
    fake_response.headers = {"location": "http://169.254.169.254/latest/meta-data/"}

    with patch("app.domains.ui_ux.tools.web._assert_fetchable_url"), \
         patch("httpx.AsyncClient.get", return_value=fake_response):
        with pytest.raises(DocFetchError, match="redirect"):
            await FetchDocs().run(FetchDocsArgs(url="http://example.com/"))


@pytest.mark.asyncio
async def test_fetch_docs_rejects_unsupported_content_type(run):
    fake_response = AsyncMock()
    fake_response.is_redirect = False
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "application/octet-stream"}
    fake_response.content = b"\x00\x01\x02"

    with patch("app.domains.ui_ux.tools.web._assert_fetchable_url"), \
         patch("httpx.AsyncClient.get", return_value=fake_response):
        with pytest.raises(DocFetchError, match="content-type"):
            await FetchDocs().run(FetchDocsArgs(url="http://example.com/binary"))


# --- fetch_docs through the full M2.3 executor: SSRF failure surfaces cleanly ---

@pytest.mark.asyncio
async def test_ssrf_blocked_fetch_surfaces_as_a_failed_execution_not_a_crash(run):
    registry = ToolRegistry([FetchDocs()])
    policy = ToolPolicy.allow_all(registry)
    executor = ToolExecutor(registry, policy)

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
        call = ToolCall(
            name="fetch_docs",
            args=FetchDocsArgs(url="http://169.254.169.254/"),
            raw_args={"url": "http://169.254.169.254/"},
        )
        result = await executor.execute(run, call)

    assert result.success is False
    assert "non-public" in result.output
