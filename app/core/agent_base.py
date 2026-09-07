import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from app.core.config import settings
from app.core.model_provider.base import ModelProvider
from app.core.run_context import RunContext
from app.core.token_budget import TokenBudget, plan_budget
from app.schemas.agent import AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class Agent(ABC):
    """Base class for domain agents.

    Subclasses own prompt assembly and post-processing; they never construct a
    model provider themselves — one shared instance is injected here.
    """

    domain: str = "base"

    # Tokens kept free for this domain's response — reasoning included, since the Qwen3
    # family reasons inline (CLAUDE.md §3). Deliberately no default: what a response needs
    # is a property of the *task*, not of the framework. A review is a few hundred tokens of
    # prose; one `site_gen` file is thousands. Getting it wrong is silent (the model runs out
    # of room mid-answer), so every domain states its own. See ROADMAP M4.1.
    reserved_output_tokens: ClassVar[int]

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

    def _plan_budget(
        self,
        run: RunContext,
        *,
        system: str = "",
        tool_schema: str = "",
        current_input: str = "",
    ) -> TokenBudget:
        """Plan this call's budget and record it on the run.

        Called **before every model call**, not once per run: M5.2's loop grows the
        tool-result tail each iteration, so a budget planned at run start is stale by the
        second call.
        """
        budget = plan_budget(
            profile=run.model_profile,
            configured_num_ctx=settings.model_num_ctx,
            reserved_output=self.reserved_output_tokens,
            system=system,
            tool_schema=tool_schema,
            current_input=current_input,
        )
        run.token_budget = budget.to_dict()
        logger.info(
            "run_id=%s budget window=%d reserved_output=%d fixed=%d available=%d",
            run.run_id,
            budget.total,
            budget.reserved_output,
            budget.fixed,
            budget.available,
        )
        return budget

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
