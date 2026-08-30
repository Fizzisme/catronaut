import logging

from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan

logging.basicConfig(
    level=logging.DEBUG if settings.is_dev else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx/httpcore log every frame at DEBUG, which drowns out our own logs.
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["ops"], summary="Liveness and model-backend readiness")
async def health_check(request: Request) -> dict:
    provider = request.app.state.model_provider
    backend_ok = await provider.health()
    return {
        "status": "ok" if backend_ok else "degraded",
        "env": settings.app_env,
        "model": settings.model_name,
        "model_backend": "up" if backend_ok else "down",
        "domains": request.app.state.orchestrator.domains,
    }
