import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.model_provider.base import ModelProvider
from app.core.model_provider.ollama_provider import OllamaProvider
from app.core.model_provider.openai_compat_provider import OpenAICompatProvider
from app.core.orchestrator import Orchestrator
from app.domains.registry import AGENT_REGISTRY

logger = logging.getLogger(__name__)


def _build_model_provider() -> ModelProvider:
    """Pick the backend from config. The only place either provider is constructed.

    `num_ctx` is an Ollama-only concept — an OpenAI-compatible server fixes its context
    length at launch — so it is passed on one path and not the other. `settings.
    effective_num_ctx` still drives M4.1's budget on both.
    """
    if settings.model_backend == "openai_compat":
        return OpenAICompatProvider(
            base_url=settings.openai_base_url,
            model_name=settings.model_name,
            timeout_s=settings.model_timeout_s,
            api_key=settings.openai_api_key,
            think=settings.model_think,
            reasoning_effort=settings.openai_reasoning_effort,
        )
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model_name=settings.model_name,
        num_ctx=settings.effective_num_ctx,
        timeout_s=settings.model_timeout_s,
        think=settings.model_think,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the shared model provider once, so agents never duplicate VRAM."""
    model_provider = _build_model_provider()
    orchestrator = Orchestrator(model_provider, AGENT_REGISTRY)

    app.state.model_provider = model_provider
    app.state.orchestrator = orchestrator

    profile = settings.model_profile
    logger.info(
        "started env=%s backend=%s model=%s tier=%s num_ctx=%d (profile window=%d) domains=%s",
        settings.app_env,
        settings.model_backend,
        settings.model_name,
        profile.reliability_tier,
        settings.effective_num_ctx,
        profile.context_window,
        orchestrator.domains,
    )
    if settings.model_backend == "openai_compat":
        # The window is a server launch flag there, not a per-request option, so the budget
        # is a prediction of what that server will accept rather than something we enforce.
        logger.info(
            "backend=openai_compat: num_ctx is NOT sent per request; ensure the serving "
            "engine was launched with a context length of at least %d.",
            settings.effective_num_ctx,
        )
    if settings.model_num_ctx is not None and settings.model_num_ctx < profile.context_window:
        # Not an error — this is the supported way to run a big model on a small box. But it
        # is worth saying out loud, because the symptom of forgetting it (a 262k model
        # behaving like a 4k one) is otherwise invisible.
        logger.warning(
            "MODEL_NUM_CTX=%d constrains %s below its %d-token window; %d tokens of context "
            "are unavailable. Unset it to use the model's full window.",
            settings.model_num_ctx,
            profile.name,
            profile.context_window,
            profile.context_window - settings.model_num_ctx,
        )
    elif settings.model_num_ctx is not None and settings.model_num_ctx > profile.context_window:
        logger.warning(
            "MODEL_NUM_CTX=%d exceeds the %s profile's context_window=%d; clamped to the "
            "profile. Update app/core/model_profile.py if this model really is bigger.",
            settings.model_num_ctx,
            profile.name,
            profile.context_window,
        )

    try:
        yield
    finally:
        await model_provider.aclose()
