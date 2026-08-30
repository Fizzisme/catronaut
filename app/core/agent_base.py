import logging
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.model_provider.base import ModelProvider
from app.core.run_context import RunContext
from app.schemas.agent import AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class Agent(ABC):
    """Base class for domain agents.

    Subclasses own prompt assembly and post-processing; they never construct a
    model provider themselves — one shared instance is injected here.
    """

    domain: str = "base"

    def __init__(self, model_provider: ModelProvider):
        self.model_provider = model_provider

    @abstractmethod
    async def handle(self, input: AgentInput) -> AgentOutput:
        ...

    def _new_run_context(self, session_id: str | None = None) -> RunContext:
        return RunContext(
            domain=self.domain,
            model_profile=settings.model_profile,
            session_id=session_id,
        )

    def _build_output(self, run: RunContext, raw: dict, content: str) -> AgentOutput:
        run.usage = self.model_provider.extract_usage(raw)
        logger.info(
            "run_id=%s domain=%s done prompt_tokens=%d response_tokens=%d duration_s=%.1f",
            run.run_id,
            run.domain,
            run.usage.prompt_tokens,
            run.usage.response_tokens,
            run.usage.duration_s,
        )
        return AgentOutput(
            run_id=run.run_id,
            result=content,
            model=raw.get("model", ""),
            raw=raw if settings.expose_raw_response else None,
        )
