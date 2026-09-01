"""Static lookup of Jakob Nielsen's 10 usability heuristics (ROADMAP M2.4).

Deliberately hardcoded — this is the placeholder ROADMAP M2.4 calls for, not the final
design. M6.4 (RAG) replaces this with a real corpus lookup; when it lands, this file and
`HeuristicTopic` should be deleted, not extended.
"""

from typing import Literal

from pydantic import BaseModel

from app.core.tools.base import Tool

HeuristicTopic = Literal[
    "visibility_of_status",
    "match_real_world",
    "user_control",
    "consistency_standards",
    "error_prevention",
    "recognition_over_recall",
    "flexibility_efficiency",
    "aesthetic_minimalist",
    "error_recovery",
    "help_documentation",
]

# One-sentence summaries in our own words, not copied verbatim from any source.
_HEURISTICS: dict[str, str] = {
    "visibility_of_status": (
        "Visibility of system status — keep the user informed with timely, "
        "appropriate feedback for every action (loading states, confirmations, progress)."
    ),
    "match_real_world": (
        "Match between system and the real world — speak the user's language, "
        "follow real-world conventions, and present information in a natural, logical order."
    ),
    "user_control": (
        "User control and freedom — support undo/redo and a clear way out of an "
        "unwanted state (like a mistaken action) without a forced, lengthy process."
    ),
    "consistency_standards": (
        "Consistency and standards — do not make users guess whether different words, "
        "situations, or actions mean the same thing; follow platform conventions."
    ),
    "error_prevention": (
        "Error prevention — design to prevent problems before they occur, or catch them "
        "and offer a confirmation before the user commits to a risky action."
    ),
    "recognition_over_recall": (
        "Recognition rather than recall — minimize memory load by making objects, "
        "actions, and options visible; instructions should be easy to retrieve when needed."
    ),
    "flexibility_efficiency": (
        "Flexibility and efficiency of use — offer accelerators (shortcuts, defaults) "
        "invisible to novices but that let expert users tailor frequent actions."
    ),
    "aesthetic_minimalist": (
        "Aesthetic and minimalist design — interfaces should not contain irrelevant or "
        "rarely needed information; every extra unit of content competes with the relevant ones."
    ),
    "error_recovery": (
        "Help users recognize, diagnose, and recover from errors — error messages should "
        "be in plain language, precisely indicate the problem, and suggest a solution."
    ),
    "help_documentation": (
        "Help and documentation — even though a system is better usable without it, "
        "any needed help should be easy to search, focused on the user's task, and concrete."
    ),
}


class LookupArgs(BaseModel):
    topic: HeuristicTopic


class LookupHeuristic(Tool):
    name = "lookup_heuristic"
    description = "Look up a UI/UX usability heuristic by topic."
    args_schema = LookupArgs
    read_only = True
    timeout_s = 2.0

    async def run(self, args: LookupArgs) -> str:
        return _HEURISTICS[args.topic]
