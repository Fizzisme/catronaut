from app.core.agent_base import Agent
from app.core.exceptions import UnknownDomainError
from app.core.model_provider.base import ModelProvider


class Orchestrator:
    """Owns one agent instance per domain, all sharing a single model provider."""

    def __init__(
        self,
        model_provider: ModelProvider,
        agent_types: dict[str, type[Agent]],
    ):
        self._agents: dict[str, Agent] = {
            domain: agent_type(model_provider)
            for domain, agent_type in agent_types.items()
        }

    def get_agent(self, domain: str) -> Agent:
        agent = self._agents.get(domain)
        if agent is None:
            known = ", ".join(sorted(self._agents)) or "none"
            raise UnknownDomainError(f"Unknown domain '{domain}'. Registered: {known}")
        return agent

    @property
    def domains(self) -> list[str]:
        return sorted(self._agents)
