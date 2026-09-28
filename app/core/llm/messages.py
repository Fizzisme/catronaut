"""Provider-neutral message model for trajectories (ROADMAP principle 6).

Wire formats are produced from these types by the client; nothing here depends on a provider.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ToolCall(_Frozen):
    id: str
    name: str
    # Raw JSON exactly as the model produced it; schema validation belongs to the tool layer (M1.3)
    arguments: str


class SystemMessage(_Frozen):
    role: Literal["system"] = "system"
    content: str


class UserMessage(_Frozen):
    role: Literal["user"] = "user"
    content: str


class AssistantMessage(_Frozen):
    role: Literal["assistant"] = "assistant"
    content: str = ""
    # Sent back in history so the rendered prefix stays identical between turns (ADR-0001 D2)
    reasoning: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class ToolResultMessage(_Frozen):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: str


Message = Annotated[
    SystemMessage | UserMessage | AssistantMessage | ToolResultMessage,
    Field(discriminator="role"),
]
