from fastapi import APIRouter, Request

from app.schemas.agent import AgentInput, AgentOutput

router = APIRouter()


@router.post("/analyze", response_model=AgentOutput, summary="Analyze a UI")
async def analyze(payload: AgentInput, request: Request) -> AgentOutput:
    agent = request.app.state.orchestrator.get_agent("ui_ux")
    return await agent.handle(payload)
