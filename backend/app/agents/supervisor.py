"""
Supervisor Agent — routing decision + doctor burnout predictor.
"""
from __future__ import annotations
from app.agents.state import AgentState
from app.core.config import settings


async def supervisor_node(state: AgentState) -> dict:
    qa_result = state.get("qa_result")
    soap_note = state.get("soap_note")

    if not qa_result or not soap_note:
        next_step = "human_review"
        reasoning = "Incomplete processing — manual review required"
    elif qa_result["needs_review"]:
        next_step = "human_review"
        reasoning = (
            f"QA flagged {len(qa_result['flags'])} claims. "
            f"Confidence: {qa_result['confidence']:.0%}. "
            "Doctor must verify highlighted sections before approval."
        )
    else:
        next_step = "auto_approve"
        reasoning = (
            f"QA passed with {qa_result['confidence']:.0%} confidence. "
            "Note auto-drafted — doctor can approve with one click."
        )

    from app.services.burnout_service import compute_session_burnout_contribution
    burnout_contribution = await compute_session_burnout_contribution(
        doctor_id=state.get("doctor_id", "unknown"),
        audio_duration=0.0,
    )

    return {
        "next_step": next_step,
        "supervisor_reasoning": reasoning,
        "burnout_score": burnout_contribution.get("burnout_score", 0.0),
        "burnout_alert": burnout_contribution.get("alert", False),
    }


def route_from_supervisor(state: AgentState) -> str:
    return state.get("next_step", "human_review")
