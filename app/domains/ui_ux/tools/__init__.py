"""The `ui_ux` domain's tool pack (ROADMAP M2.4).

`TOOLS` is a ready-made list for `ToolRegistry(TOOLS)` once the loop (M5.1/M5.2) wires
tools into an agent. Nothing does that yet — see CLAUDE.md's tool-layer section.
"""

from app.domains.ui_ux.tools.accessibility import CheckContrast
from app.domains.ui_ux.tools.heuristics import LookupHeuristic
from app.domains.ui_ux.tools.report import FormatReview
from app.domains.ui_ux.tools.web import FetchDocs

TOOLS = [CheckContrast(), LookupHeuristic(), FormatReview(), FetchDocs()]
