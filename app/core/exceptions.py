"""Application exception hierarchy and the FastAPI handlers that map it to HTTP."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class CatronautError(Exception):
    """Base class for every error raised by this service."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnknownDomainError(CatronautError):
    """Requested agent domain is not registered."""

    status_code = 404
    code = "unknown_domain"


class ProviderError(CatronautError):
    """The model backend failed, timed out, or returned an unusable payload."""

    status_code = 502
    code = "provider_error"


class DomainError(CatronautError):
    """A domain agent could not fulfil the request."""

    status_code = 422
    code = "domain_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CatronautError)
    async def _handle(request: Request, exc: CatronautError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
