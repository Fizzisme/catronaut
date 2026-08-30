import logging

from app.core.agent_base import Agent
from app.core.config import settings
from app.domains.ui_ux.prompts import SYSTEM_PROMPT
from app.schemas.agent import AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class UIUXAgent(Agent):
    domain = "ui_ux"

    async def handle(self, input: AgentInput) -> AgentOutput:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        user_message: dict = {"role": "user", "content": input.prompt}
        if input.image_base64:
            if not settings.model_profile.supports_vision:
                # Non-blocking by design (CLAUDE.md decision): the field stays accepted so
                # requests don't need to change per model; Ollama just ignores `images` on a
                # text-only model. This is only a diagnostic breadcrumb.
                logger.info(
                    "image_base64 provided but model=%s has no vision support; Ollama will "
                    "ignore it",
                    settings.model_name,
                )
            # Ollama's multimodal message format.
            user_message["images"] = [input.image_base64]
        messages.append(user_message)

        raw = await self.model_provider.chat(messages=messages)
        content = self.model_provider.extract_content(raw)

        return self._build_output(raw, content)
