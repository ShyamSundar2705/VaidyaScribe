"""
LangGraph multi-agent graph for VaidyaScribe.
Pipeline: stt → translation → ner → soap_generator → qa → supervisor → END
"""
from __future__ import annotations
import uuid
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import AsyncRedisSaver
from app.agents.state import AgentState
from app.agents.stt_agent import stt_agent_node
from app.agents.translation_agent import translation_agent_node
from app.agents.ner_agent import ner_agent_node
from app.agents.soap_generator import soap_generator_node
from app.agents.qa_agent import qa_agent_node
from app.agents.supervisor import supervisor_node, route_from_supervisor
from app.core.config import settings

_graph = None


async def build_graph():
    checkpointer = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
    builder = StateGraph(AgentState)
    builder.add_node("stt", stt_agent_node)
    builder.add_node("translation", translation_agent_node)
    builder.add_node("ner", ner_agent_node)
    builder.add_node("soap_generator", soap_generator_node)
    builder.add_node("qa", qa_agent_node)
    builder.add_node("supervisor", supervisor_node)
    builder.set_entry_point("stt")
    builder.add_edge("stt", "translation")
    builder.add_edge("translation", "ner")
    builder.add_edge("ner", "soap_generator")
    builder.add_edge("soap_generator", "qa")
    builder.add_edge("qa", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"human_review": END, "auto_approve": END},
    )
    return builder.compile(checkpointer=checkpointer)


async def get_graph():
    global _graph
    if _graph is None:
        _graph = await build_graph()
    return _graph


async def run_pipeline(session_id: str, doctor_id: str, audio_path: str) -> AgentState:
    graph = await get_graph()
    run_id = str(uuid.uuid4())
    initial: AgentState = {
        "session_id": session_id, "doctor_id": doctor_id, "audio_path": audio_path,
        "transcript_segments": [], "raw_transcript": None, "language_mix": None,
        "english_transcript": None, "tamil_original": None, "entities": None,
        "soap_note": None, "tamil_patient_summary": None, "qa_result": None,
        "next_step": None, "supervisor_reasoning": None, "burnout_score": None,
        "burnout_alert": False, "messages": [], "error": None,
    }
    config = {"configurable": {"thread_id": run_id}}
    return await graph.ainvoke(initial, config=config)
