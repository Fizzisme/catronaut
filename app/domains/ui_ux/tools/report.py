"""Structured report formatter — the third `ui_ux` tool (ROADMAP M2.4)."""

from pydantic import BaseModel, Field

from app.core.tools.base import Tool


class ReportArgs(BaseModel):
    summary: str
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class FormatReview(Tool):
    name = "format_review"
    description = "Format UI/UX findings into a structured report."
    args_schema = ReportArgs
    read_only = True
    timeout_s = 2.0

    async def run(self, args: ReportArgs) -> str:
        sections = [f"## Summary\n{args.summary}"]
        if args.issues:
            sections.append("## Issues\n" + "\n".join(f"- {i}" for i in args.issues))
        if args.recommendations:
            sections.append(
                "## Recommendations\n" + "\n".join(f"- {r}" for r in args.recommendations)
            )
        return "\n\n".join(sections)
