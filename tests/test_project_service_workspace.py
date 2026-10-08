import asyncio
import json
from typing import Any

import httpx2
import pytest

from app.core.workspace.base import FlushResult
from app.core.workspace.errors import WorkspaceConflict
from app.core.workspace.project_service import (
    ProjectServiceConfig,
    ProjectServiceError,
    ProjectServiceWorkspace,
)
from app.core.workspace.quota import WriteQuota

PROJECT = "p1"
LEASE_ID = "lease-secret"


def envelope(status: int, data: Any, code: str = "OK") -> httpx2.Response:
    return httpx2.Response(status, json={"success": status < 400, "code": code, "data": data})


def failure(status: int, code: str) -> httpx2.Response:
    body = {"success": False, "code": code, "message": f"{code} message", "data": None}
    return httpx2.Response(status, json=body)


class FakeProjectService:
    """project-service's files and lease endpoints, in memory."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = dict(files or {})
        self.revision = 12
        self.base_revision = 12
        self.leased = False
        self.requests: list[httpx2.Request] = []
        # Sent instead of the normal answer to the next request on that route
        self.overrides: dict[tuple[str, str], list[httpx2.Response | Exception]] = {}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        route = (request.method, request.url.path)
        queued = self.overrides.get(route)
        if queued:
            answer = queued.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        match route:
            case ("POST", "/p1/lease"):
                if self.leased:
                    return failure(423, "PROJECT_LEASED")
                self.leased = True
                return envelope(201, {"leaseId": LEASE_ID, "baseRevision": self.base_revision})
            case ("GET", "/p1/files"):
                files = [{"path": p, "content": c} for p, c in sorted(self.files.items())]
                return envelope(200, {"revision": self.revision, "files": files})
            case ("POST", "/p1/files/changes"):
                return self._save(request)
            case ("PUT", "/p1/lease/lease-secret"):
                return envelope(200, {"leaseId": LEASE_ID, "baseRevision": self.base_revision})
            case ("DELETE", "/p1/lease/lease-secret"):
                self.leased = False
                return httpx2.Response(204)
            case _:
                return failure(404, "NOT_FOUND")

    def _save(self, request: httpx2.Request) -> httpx2.Response:
        if request.headers.get("If-Match") != f'"{self.revision}"':
            return failure(412, "FILES_STALE_REVISION")
        if request.headers.get("Lease-Id") != LEASE_ID:
            return failure(423, "PROJECT_LEASED")
        for change in json.loads(request.content)["changes"]:
            if change["op"] == "PUT":
                self.files[change["path"]] = change["content"]
            else:
                del self.files[change["path"]]
        self.revision += 1
        return envelope(200, {"revision": self.revision, "files": []})

    def calls(self) -> list[str]:
        return [f"{request.method} {request.url.path}" for request in self.requests]


def workspace(
    server: FakeProjectService, quota: WriteQuota | None = None, **config: Any
) -> tuple[ProjectServiceWorkspace, list[float]]:
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(server))
    ws = ProjectServiceWorkspace(
        ProjectServiceConfig(base_url="http://project-service/", **config),
        client,
        project_id=PROJECT,
        user_id="user-1",
        run_id="run_abc",
        quota=quota,
        sleep=sleep,
        rand=lambda: 1.0,
    )
    return ws, delays


def test_open_takes_the_lease_then_loads_the_tree() -> None:
    server = FakeProjectService({"app/page.tsx": "home"})
    server.base_revision = 10
    ws, _ = workspace(server)

    async def run() -> None:
        async with ws:
            assert ws.base_revision == 10
            assert ws.read("app/page.tsx") == "home"

    asyncio.run(run())

    assert server.calls() == [
        "POST /p1/lease",
        "GET /p1/files",
        "DELETE /p1/lease/lease-secret",
    ]
    assert json.loads(server.requests[0].content) == {
        "holder": "ai-service",
        "runId": "run_abc",
        "ttlSeconds": 120,
    }
    assert server.requests[1].url.params["include"] == "content"
    assert all(request.headers["X-User-ID"] == "user-1" for request in server.requests)


def test_each_flush_stores_one_revision_with_the_previous_one_as_if_match() -> None:
    server = FakeProjectService({"old.ts": "old"})
    ws, _ = workspace(server)

    async def run() -> list[FlushResult | None]:
        async with ws:
            ws.write("app/page.tsx", "page")
            ws.delete("old.ts")
            first = await ws.flush("run:run_abc step 1")
            ws.write("app/page.tsx", "page 2")
            second = await ws.flush("run:run_abc step 2")
            return [first, second]

    assert asyncio.run(run()) == [
        FlushResult(13, ("app/page.tsx", "old.ts")),
        FlushResult(14, ("app/page.tsx",)),
    ]
    assert server.files == {"app/page.tsx": "page 2"}

    saves = [request for request in server.requests if request.url.path.endswith("/changes")]
    assert [request.headers["If-Match"] for request in saves] == ['"12"', '"13"']
    assert json.loads(saves[0].content) == {
        "changes": [
            {"op": "PUT", "path": "app/page.tsx", "content": "page"},
            {"op": "DELETE", "path": "old.ts"},
        ],
        "label": "run:run_abc step 1",
        "source": {"kind": "AGENT", "runId": "run_abc"},
    }


def test_close_stores_what_is_left_as_the_end_of_the_run() -> None:
    server = FakeProjectService()
    ws, _ = workspace(server)

    async def run() -> None:
        async with ws:
            ws.write("a.ts", "a")

    asyncio.run(run())

    assert server.files == {"a.ts": "a"}
    save = next(request for request in server.requests if request.url.path.endswith("/changes"))
    assert json.loads(save.content)["label"] == "run:run_abc end"
    assert not server.leased


def test_a_leased_project_cannot_be_opened() -> None:
    server = FakeProjectService()
    server.leased = True
    ws, _ = workspace(server)

    with pytest.raises(WorkspaceConflict, match="leased by someone else"):
        asyncio.run(ws.open())

    assert server.calls() == ["POST /p1/lease"]


def test_a_failed_tree_read_releases_the_lease() -> None:
    server = FakeProjectService()
    server.overrides[("GET", "/p1/files")] = [failure(403, "PROJECT_FORBIDDEN")]
    ws, _ = workspace(server)

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(ws.open())

    assert exc_info.value.status == 403
    assert exc_info.value.code == "PROJECT_FORBIDDEN"
    assert not server.leased


def test_a_stale_revision_fails_the_run_and_still_releases_the_lease() -> None:
    server = FakeProjectService()
    ws, _ = workspace(server)

    async def run() -> None:
        async with ws:
            ws.write("a.ts", "a")
            # Someone else stored a revision while the run was working
            server.revision += 1

    with pytest.raises(WorkspaceConflict, match="someone else changed") as exc_info:
        asyncio.run(run())

    assert isinstance(exc_info.value, ProjectServiceError)
    assert exc_info.value.status == 412
    assert server.files == {}
    assert not server.leased


def test_storage_unavailable_is_retried_with_the_same_if_match() -> None:
    server = FakeProjectService()
    server.overrides[("POST", "/p1/files/changes")] = [
        failure(503, "FILES_STORAGE_UNAVAILABLE"),
        httpx2.ConnectError("reset"),
    ]
    ws, delays = workspace(server)

    async def run() -> FlushResult | None:
        async with ws:
            ws.write("a.ts", "a")
            return await ws.flush("step 1")

    assert asyncio.run(run()) == FlushResult(13, ("a.ts",))
    saves = [request for request in server.requests if request.url.path.endswith("/changes")]
    assert [request.headers["If-Match"] for request in saves] == ['"12"', '"12"', '"12"']
    # Full jitter with rand() = 1: the cap doubles each attempt
    assert delays == [0.5, 1.0]


def test_storage_unavailable_gives_up_after_max_attempts() -> None:
    server = FakeProjectService()
    server.overrides[("POST", "/p1/files/changes")] = [
        failure(503, "FILES_STORAGE_UNAVAILABLE") for _ in range(3)
    ]
    ws, _ = workspace(server)

    async def run() -> None:
        async with ws:
            ws.write("a.ts", "a")
            await ws.flush("step 1")

    with pytest.raises(ProjectServiceError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status == 503


def test_a_lost_lease_stops_every_write() -> None:
    server = FakeProjectService()
    server.overrides[("PUT", "/p1/lease/lease-secret")] = [failure(404, "LEASE_NOT_FOUND")]
    ws, _ = workspace(server, renew_interval_s=0.01)

    async def run() -> None:
        async with ws:
            ws.write("a.ts", "a")
            await asyncio.sleep(0.05)
            await ws.flush("step 1")

    with pytest.raises(WorkspaceConflict, match="lease was lost"):
        asyncio.run(run())

    # Nothing was stored after the loss, not even on close
    assert server.files == {}
    assert server.calls()[-1] == "DELETE /p1/lease/lease-secret"


def test_the_lease_is_renewed_while_the_run_works() -> None:
    server = FakeProjectService()
    ws, _ = workspace(server, renew_interval_s=0.01)

    async def run() -> None:
        async with ws:
            await asyncio.sleep(0.05)

    asyncio.run(run())

    assert "PUT /p1/lease/lease-secret" in server.calls()
    assert server.calls()[-1] == "DELETE /p1/lease/lease-secret"


def test_large_flushes_are_split_into_requests_of_the_allowed_size() -> None:
    server = FakeProjectService()
    ws, _ = workspace(server, WriteQuota(max_batch_changes=2))

    async def run() -> FlushResult | None:
        async with ws:
            for n in range(5):
                ws.write(f"f{n}.ts", "x")
            return await ws.flush("step 1")

    result = asyncio.run(run())

    assert result is not None
    assert result.revision == 15
    assert len(result.paths) == 5
