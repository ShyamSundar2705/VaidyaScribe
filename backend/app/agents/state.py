from __future__ import annotations
from typing import Annotated, Optional, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
import operator


class TranscriptSegment(TypedDict):
    text: str
    lang: str              # "ta" | "en" | "mixed"
    confidence: float
    start_time: float
    end_time: float


class ExtractedEntities(TypedDict):
    chief_complaint: str
    symptoms: list[str]
    duration: str
    medications: list[dict]  # [{name, dose, frequency}]
    vitals: dict             # {bp, hr, temp, spo2, weight}
    allergies: list[str]
    icd10_codes: list[str]
    plan_keywords: list[str]


class SOAPNote(TypedDict):
    subjective: str
    objective: str
    assessment: str
    plan: str
    icd10_codes: list[str]
    confidence: float


class QAResult(TypedDict):
    confidence: float
    flags: list[dict]        # [{field, claim, reason}]
    needs_review: bool
    summary: str


class AgentState(TypedDict):
    # Input
    session_id: str
    doctor_id: str
    audio_path: Optional[str]

    # STT agent output
    transcript_segments: Annotated[list[TranscriptSegment], operator.add]
    raw_transcript: Optional[str]
    language_mix: Optional[str]               # "tamil-english" | "english" | "tamil"

    # Translation agent output
    english_transcript: Optional[str]
    tamil_original: Optional[str]             # preserved Tamil text

    # NER agent output
    entities: Optional[ExtractedEntities]

    # SOAP generator output
    soap_note: Optional[SOAPNote]

    # Tamil summary output
    tamil_patient_summary: Optional[str]

    # QA agent output
    qa_result: Optional[QAResult]

    # Supervisor routing
    next_step: Optional[Literal["human_review", "auto_approve", "rejected"]]
    supervisor_reasoning: Optional[str]

    # Burnout
    burnout_score: Optional[float]
    burnout_alert: bool

    # Messages log (for LangSmith tracing)
    messages: Annotated[list[BaseMessage], operator.add]

    # Error handling
    error: Optional[str]
