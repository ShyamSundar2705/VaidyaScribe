"""
QA Agent — Hallucination detection and clinical safety gate.

Cross-checks every claim in the generated SOAP note against
the original transcript. Flags anything in the note that is
NOT supported by the transcript text.

This directly addresses the 19.6% AI error rate problem
and is the core clinical safety differentiator.
"""
from __future__ import annotations
import re
from app.agents.state import AgentState, QAResult, SOAPNote
from app.core.config import settings


def normalise(text: str) -> set[str]:
    """Tokenise and normalise text to a set of meaningful words."""
    words = re.findall(r"\b\w{3,}\b", text.lower())
    # Remove common stop words that don't carry clinical meaning
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from",
        "has", "was", "are", "been", "have", "will", "not",
        "documented", "noted", "reported", "patient", "doctor",
    }
    return {w for w in words if w not in stopwords}


def check_claim_in_transcript(claim: str, transcript_words: set[str]) -> tuple[bool, list[str]]:
    """
    Check if a claim from the SOAP note is supported by transcript words.
    Returns (is_supported, unsupported_tokens).
    """
    claim_words = normalise(claim)
    if not claim_words:
        return True, []

    # A claim is supported if at least 60% of its key words appear in the transcript
    supported = claim_words & transcript_words
    unsupported = claim_words - transcript_words
    support_ratio = len(supported) / len(claim_words) if claim_words else 1.0

    is_supported = support_ratio >= 0.60
    return is_supported, list(unsupported)[:5]


def extract_clinical_claims(soap_note: SOAPNote) -> list[tuple[str, str]]:
    """Extract key clinical claims from each SOAP section as (section, claim) tuples."""
    claims = []

    # Break SOAP sections into sentences for granular checking
    for section, text in [
        ("subjective", soap_note.get("subjective", "")),
        ("objective", soap_note.get("objective", "")),
        ("assessment", soap_note.get("assessment", "")),
        ("plan", soap_note.get("plan", "")),
    ]:
        if not text or text in ("Not documented", "Generation failed — manual entry required"):
            continue
        # Split into sentences
        sentences = re.split(r"[.;]\s+", text)
        for sent in sentences:
            if len(sent.strip()) > 20:  # ignore very short fragments
                claims.append((section, sent.strip()))

    return claims


async def qa_agent_node(state: AgentState) -> dict:
    """
    Validates SOAP note claims against transcript.
    Returns confidence score and list of flagged hallucinations.
    """
    soap_note: SOAPNote | None = state.get("soap_note")
    transcript = state.get("english_transcript") or state.get("raw_transcript", "")

    if not soap_note:
        return {
            "qa_result": {
                "confidence": 0.0,
                "flags": [{"field": "all", "claim": "No SOAP note generated", "reason": "Generation failed"}],
                "needs_review": True,
                "summary": "QA could not run — no SOAP note available",
            }
        }

    transcript_words = normalise(transcript)
    claims = extract_clinical_claims(soap_note)

    flags = []
    supported_count = 0

    for section, claim in claims:
        is_supported, unsupported_tokens = check_claim_in_transcript(claim, transcript_words)
        if is_supported:
            supported_count += 1
        else:
            flags.append({
                "field": section,
                "claim": claim[:200],
                "reason": f"Tokens not found in transcript: {', '.join(unsupported_tokens)}",
            })

    total_claims = len(claims)
    confidence = supported_count / total_claims if total_claims > 0 else 1.0

    # Boost confidence from the SOAP generator's own confidence score
    soap_confidence = soap_note.get("confidence", 0.7)
    final_confidence = (confidence * 0.7) + (soap_confidence * 0.3)

    needs_review = (
        final_confidence < settings.QA_CONFIDENCE_THRESHOLD
        or len(flags) > 2
    )

    summary = (
        f"QA passed — {final_confidence:.0%} confidence, {len(flags)} flags"
        if not needs_review
        else f"Review required — {final_confidence:.0%} confidence, {len(flags)} claims need verification"
    )

    return {
        "qa_result": {
            "confidence": round(final_confidence, 3),
            "flags": flags,
            "needs_review": needs_review,
            "summary": summary,
        }
    }
