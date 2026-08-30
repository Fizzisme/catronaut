from app.core.agent_base import Agent
from app.domains.ui_ux.prompts import SYSTEM_PROMPT
from app.schemas.agent import AgentInput, AgentOutput


class UIUXAgent(Agent):
    domain = "ui_ux"

    async def handle(self, input: AgentInput) -> AgentOutput:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        user_message: dict = {"role": "user", "content": input.prompt}
        if input.image_base64:
            # Ollama's multimodal message format. Silently ignored by text-only
            # models such as qwen3:4b — vision is a production-model capability.
            user_message["images"] = [input.image_base64]
        messages.append(user_message)

        raw = await self.model_provider.chat(messages=messages)
        content = self.model_provider.extract_content(raw)

        return self._build_output(raw, content)
