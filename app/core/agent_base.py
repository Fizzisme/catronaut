from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.model_provider.base import ModelProvider
from app.schemas.agent import AgentInput, AgentOutput


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

    def _build_output(self, raw: dict, content: str) -> AgentOutput:
        return AgentOutput(
            result=content,
            model=raw.get("model", ""),
            raw=raw if settings.expose_raw_response else None,
        )
