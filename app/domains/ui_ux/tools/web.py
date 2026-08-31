"""Fetch a public web page's readable text (ROADMAP M2.4's fourth tool).

The one tool in this pack that makes an outbound request — a deliberate exception to
M8.2's original "no sandbox needed" assessment for this pack. Mitigated the way
OpenDesign's `assertAndFetchExternalAsset` does it (see ROADMAP M8.2 for the writeup of
that pattern): resolve the hostname first, reject any resolved address that is
loopback/private/link-local/reserved *before* connecting, and never follow a redirect
blindly. This is SSRF mitigation, not sandboxing — it does not touch M8.3's trigger list
(no code execution, no filesystem access).
"""

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, field_validator

from app.core.tools.base import Tool

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_DOWNLOAD_BYTES = 200_000  # raw bytes read before giving up on a huge page
_MAX_OUTPUT_CHARS = 4_000  # keep well under ToolExecutor's 2000-default is not assumed;
# this tool caps its own output too so a verbose page doesn't rely solely on the
# executor's generic truncation to stay reasonable.


class DocFetchError(Exception):
    """Raised for any fetch failure — blocked address, timeout, bad content type, HTTP
    error. Caught by ToolExecutor (M2.3), which turns it into a failed
    ToolExecutionResult; never propagates to the caller."""


def _assert_public_hostname(hostname: str) -> None:
    """Resolve `hostname` and reject it if ANY resolved address is not a public,
    routable unicast address. Checked before the request is made, so a hostname that
    resolves to 127.0.0.1, 169.254.169.254 (cloud metadata), 10.x/172.16.x/192.168.x,
    or similar never reaches `httpx`."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise DocFetchError(f"could not resolve host {hostname!r}: {exc}") from exc

    for info in infos:
        raw_addr = info[4][0]
        try:
            addr = ipaddress.ip_address(raw_addr)
        except ValueError:
            continue
        if (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise DocFetchError(
                f"{hostname!r} resolves to a non-public address ({raw_addr}); refusing to fetch"
            )


def _assert_fetchable_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise DocFetchError(f"unsupported URL scheme {parsed.scheme!r}; only http/https allowed")
    if not parsed.hostname:
        raise DocFetchError("URL has no hostname")
    _assert_public_hostname(parsed.hostname)


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text: drop tags and script/style content, keep everything else.
    Stdlib only — no new dependency for what is, at this stage, a single tool."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return "\n".join(self._chunks)


def _extract_text(content_type: str, body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    if "html" in content_type:
        parser = _TextExtractor()
        parser.feed(text)
        return parser.text()
    return text  # text/plain, text/markdown, ...


class FetchDocsArgs(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def _looks_like_url(cls, value: str) -> str:
        # Cheap shape check at the M2.2 validation layer, eligible for the one repair
        # turn. The real security check (_assert_fetchable_url) runs in run(), where a
        # DNS lookup belongs — not in a Pydantic validator.
        if not value.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return value


class FetchDocs(Tool):
    name = "fetch_docs"
    description = "Fetch a public web page and return its readable text content."
    args_schema = FetchDocsArgs
    read_only = True
    timeout_s = 15.0

    async def run(self, args: FetchDocsArgs) -> str:
        _assert_fetchable_url(args.url)

        async with httpx.AsyncClient(follow_redirects=False) as client:
            try:
                response = await client.get(
                    args.url,
                    timeout=self.timeout_s,
                    headers={"User-Agent": "catronaut-ui-ux-fetch-docs/1.0"},
                )
            except httpx.HTTPError as exc:
                raise DocFetchError(f"request failed: {exc}") from exc

        if response.is_redirect:
            # A redirect could point anywhere, including a private address — refuse
            # rather than following it blindly. The model can retry with the
            # Location header's target if it chooses to.
            location = response.headers.get("location", "<none>")
            raise DocFetchError(f"got a redirect to {location!r}; not followed")
        if response.status_code >= 400:
            raise DocFetchError(f"HTTP {response.status_code} fetching {args.url}")

        content_type = response.headers.get("content-type", "").lower()
        if not any(kind in content_type for kind in ("text/html", "text/plain", "text/markdown")):
            raise DocFetchError(f"unsupported content-type {content_type!r}")

        body = response.content[:_MAX_DOWNLOAD_BYTES]
        text = _extract_text(content_type, body)
        return text[:_MAX_OUTPUT_CHARS]
