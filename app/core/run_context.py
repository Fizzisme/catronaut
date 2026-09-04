"""Per-request run context.

Created once per incoming request and threaded through the agent. `token_budget` is populated
by M4.1's allocator; `steps` (M5.2, the loop trace) and `tool_results` (M2.3) still wait on
their milestones to land. Its job today is narrower: give every request a stable `run_id` for
log correlation (used now; structured logging around it lands in M1.5) and a single object
those later milestones can extend without changing every call site that constructs one.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.model_profile import ModelProfile
from app.core.model_provider.base import RunUsage


@dataclass
class RunContext:
    domain: str
    model_profile: ModelProfile
    session_id: str | None = None  # ROADMAP M4.4 — no session store yet, always None today
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Set by Agent._build_output once the model call completes (ROADMAP M1.5).
    usage: RunUsage | None = None

    # Set by Agent._new_run_context via app.core.token_budget.allocate_budget (ROADMAP M4.1).
    # Nothing reads the slots yet — M4.2's assembly pipeline and M4.3's truncation are the
    # first consumers.
    token_budget: dict | None = None

    # Populated by later milestones. Present now so those milestones extend one object
    # instead of threading new parameters through every agent/provider call site.
    steps: list = field(default_factory=list)  # ROADMAP M5.2 — loop step trace
    tool_results: list = field(default_factory=list)  # ROADMAP M2.3
