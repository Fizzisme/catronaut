import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.model_provider.ollama_provider import OllamaProvider
from app.core.orchestrator import Orchestrator
from app.domains.registry import AGENT_REGISTRY

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the shared model provider once, so agents never duplicate VRAM."""
    model_provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model_name=settings.model_name,
        num_ctx=settings.model_num_ctx,
        timeout_s=settings.model_timeout_s,
        think=settings.model_think,
    )
    orchestrator = Orchestrator(model_provider, AGENT_REGISTRY)

    app.state.model_provider = model_provider
    app.state.orchestrator = orchestrator

    profile = settings.model_profile
    logger.info(
        "started env=%s model=%s tier=%s num_ctx=%d domains=%s",
        settings.app_env,
        settings.model_name,
        profile.reliability_tier,
        settings.model_num_ctx,
        orchestrator.domains,
    )
    if settings.model_num_ctx > profile.context_window:
        logger.warning(
            "MODEL_NUM_CTX=%d exceeds the %s profile's context_window=%d; Ollama may reject "
            "or clamp this request.",
            settings.model_num_ctx,
            profile.name,
            profile.context_window,
        )

    try:
        yield
    finally:
        await model_provider.aclose()
