from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    prompt: str = Field(min_length=1, description="Task or question for the agent.")
    image_base64: str | None = Field(
        default=None,
        description=(
            "Optional base64 screenshot. Requires a vision-capable model; "
            "qwen3:4b / qwen3:8b are text-only."
        ),
    )


class AgentOutput(BaseModel):
    run_id: str = Field(description="Correlate this response with server-side logs.")
    result: str
    model: str
    raw: dict | None = Field(
        default=None,
        description="Full provider payload. Populated in dev only.",
    )
