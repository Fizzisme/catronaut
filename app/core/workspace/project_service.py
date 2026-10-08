"""ProjectServiceWorkspace (M1.4): the working copy of a Catalog Project in project-service.

The HTTP side follows ref/ai-service-integration.md (project-service `5396dd9`): take the lease,
read the tree, store each flush as one revision with `If-Match` and `Lease-Id`, renew the lease
in the background, release it at the end. ADR-0003 Decision 8: a `412` or `423` during a run
means someone else changed the project, so the run stops instead of overwriting their change.
"""

import asyncio
import contextlib
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.workspace.base import FileChange, FlushResult, Workspace
from app.core.workspace.errors import WorkspaceConflict
from app.core.workspace.quota import WriteQuota

_HOLDER = "ai-service"
_MAX_LABEL = 200


class ProjectServiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Internal network address, without the gateway's `/api/projects` prefix
    base_url: str
    # The lease expires this long after the last renewal; project-service allows 30..3600
    lease_ttl_s: int = Field(default=120, ge=30, le=3600)
    # Renew this often; None = a third of the TTL, as the integration guide recommends
    renew_interval_s: float | None = None
    # For `503 FILES_STORAGE_UNAVAILABLE` and connection failures; nothing was stored, so the
    # same request is sent again
    max_attempts: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 4.0


class ProjectServiceError(WorkspaceConflict):
    """project-service refused or failed a request; the run cannot go on."""

    def __init__(self, message: str, status: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class _Model(BaseModel):
    """project-service sends camelCase JSON (`leaseId`, `baseRevision`)."""

    model_config = ConfigDict(alias_generator=to_camel, frozen=True)


class _Lease(_Model):
    lease_id: str
    base_revision: int


class _TreeFile(_Model):
    path: str
    content: str


class _Tree(_Model):
    revision: int
    files: list[_TreeFile]


class _Saved(_Model):
    revision: int


class ProjectServiceWorkspace(Workspace):
    def __init__(
        self,
        config: ProjectServiceConfig,
        http_client: httpx2.AsyncClient,
        *,
        project_id: str,
        user_id: str,
        run_id: str,
        quota: WriteQuota | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        super().__init__(quota)
        self._config = config
        self._client = http_client
        self._project_id = project_id
        self._user_id = user_id
        self._run_id = run_id
        self._sleep = sleep
        self._rand = rand
        self._lease_id: str | None = None
        # Why the lease was lost; once set, nothing more is written (a write after expiry would
        # still be accepted by project-service, so the check has to be ours)
        self._lease_lost: str | None = None
        self._renewal: asyncio.Task[None] | None = None
        # The revision storage has now: the next `If-Match`. Not `base_revision`, which stays
        # at the run's start
        self._revision = 0

    async def open(self) -> None:
        body = {"holder": _HOLDER, "runId": self._run_id, "ttlSeconds": self._config.lease_ttl_s}
        response = await self._request("POST", "/lease", expected=201, json=body)
        lease = _Lease.model_validate(response.json()["data"])
        self._lease_id = lease.lease_id
        try:
            response = await self._request(
                "GET", "/files", expected=200, params={"include": "content"}
            )
        except BaseException:
            await self._release()
            raise
        tree = _Tree.model_validate(response.json()["data"])
        self._revision = tree.revision
        self._load({file.path: file.content for file in tree.files}, lease.base_revision)
        self._renewal = asyncio.create_task(self._renew_forever())

    async def flush(self, label: str) -> FlushResult | None:
        if self._lease_lost is not None:
            raise WorkspaceConflict(f"the project lease was lost: {self._lease_lost}")
        changes = self.pending()
        if not changes:
            return None
        # project-service takes at most this many changes per request. Each part is atomic; if
        # a later part fails, the run fails and the frontend reloads the stored tree
        size = self._quota.max_batch_changes
        for start in range(0, len(changes), size):
            await self._save(changes[start : start + size], label)
        self._mark_flushed()
        return FlushResult(self._revision, tuple(change.path for change in changes))

    async def close(self) -> None:
        try:
            if self._lease_lost is None:
                await self.flush(f"run:{self._run_id} end")
        finally:
            await self._release()

    async def _save(self, changes: tuple[FileChange, ...], label: str) -> None:
        body = {
            "changes": [_to_wire(change) for change in changes],
            "label": label[:_MAX_LABEL],
            "source": {"kind": "AGENT", "runId": self._run_id},
        }
        headers = {"If-Match": f'"{self._revision}"', "Lease-Id": self._lease_id or ""}
        response = await self._request(
            "POST", "/files/changes", expected=200, json=body, headers=headers
        )
        self._revision = _Saved.model_validate(response.json()["data"]).revision

    async def _renew_forever(self) -> None:
        interval = self._config.renew_interval_s or self._config.lease_ttl_s / 3
        while True:
            await asyncio.sleep(interval)
            try:
                await self._request("PUT", f"/lease/{self._lease_id}", expected=200)
            except ProjectServiceError as exc:
                if exc.status == 404:
                    self._lease_lost = "it expired or was released before it could be renewed"
                    return
                # Anything else may pass; if it lasts until the lease expires, the next renewal
                # gets the 404

    async def _release(self) -> None:
        if self._renewal is not None:
            self._renewal.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._renewal
            self._renewal = None
        if self._lease_id is None:
            return
        lease_id, self._lease_id = self._lease_id, None
        # Best effort: a lease that is not released expires within its TTL anyway
        with contextlib.suppress(ProjectServiceError):
            await self._request("DELETE", f"/lease/{lease_id}", expected=204)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected: int,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx2.Response:
        """Send a request about this project, retrying what failed without storing anything."""
        url = f"{self._config.base_url.rstrip('/')}/{self._project_id}{path}"
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers={"X-User-ID": self._user_id, **(headers or {})},
                )
            except httpx2.TransportError as exc:
                if attempt >= self._config.max_attempts:
                    raise ProjectServiceError(f"{method} {path} failed: {exc}") from exc
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code == expected:
                return response
            if response.status_code == 503 and attempt < self._config.max_attempts:
                await self._sleep(self._backoff(attempt))
                continue
            raise _error(method, path, response)

    def _backoff(self, attempt: int) -> float:
        """Full jitter: a uniform delay up to an exponentially growing cap."""
        cap = min(self._config.backoff_max, self._config.backoff_base * 2 ** (attempt - 1))
        return cap * self._rand()


def _to_wire(change: FileChange) -> dict[str, str]:
    if change.content is None:
        return {"op": "DELETE", "path": change.path}
    return {"op": "PUT", "path": change.path, "content": change.content}


def _error(method: str, path: str, response: httpx2.Response) -> ProjectServiceError:
    code, message = "", response.text
    # Errors without the JSON envelope (a proxy's HTML page) keep the raw text
    with contextlib.suppress(ValueError, AttributeError):
        body = response.json()
        code = str(body.get("code", ""))
        message = str(body.get("message", message))
    status = response.status_code
    if status == 412:
        message = f"someone else changed the project files during the run ({message})"
    elif status == 423:
        message = f"the project is leased by someone else ({message})"
    return ProjectServiceError(f"{method} {path}: {status} {code} {message}", status, code)
