"""Domain registry.

The single place a new agent domain is declared. `app/core/` stays untouched when
a domain is added: create `app/domains/<domain>/`, add one line here, and add one
router under `app/api/`.
"""

from app.core.agent_base import Agent
from app.domains.ui_ux.agent import UIUXAgent

AGENT_REGISTRY: dict[str, type[Agent]] = {
    "ui_ux": UIUXAgent,
}
