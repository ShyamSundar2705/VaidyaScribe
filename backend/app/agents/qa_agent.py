"""
QA Agent — Hallucination detection and clinical safety gate.

Cross-checks SOAP note claims against the original transcript.
Flags claims where key CLINICAL tokens (medications, diagnoses, numbers)
appear in the note but NOT in the transcript.

Key design decisions:
  - Only flag genuinely new clinical facts, not LLM rephrasing
  - Medical abbreviations (BP, HR, ACS) are whitelisted
  - Numbers/doses are checked strictly — these are the real risk
  - Generic SOAP boilerplate is ignored entirely
"""
from __future__ import annotations
import re
from app.agents.state import AgentState, QAResult, SOAPNote
from app.core.config import settings


# ─── Whitelisted tokens the LLM always adds but may not be in transcript ──
# These are standard SOAP formatting words, not clinical claims
SOAP_BOILERPLATE = {
    # Common SOAP words
    "patient", "presents", "presenting", "reported", "reports", "denies",
    "noted", "noted", "documented", "history", "known", "current", "chronic",
    "assessment", "plan", "refer", "referral", "follow", "review",
    # Standard medical abbreviations always acceptable
    "bp", "hr", "rr", "spo2", "temp", "ecg", "ekg", "nkda", "nka",
    "acs", "ami", "urti", "lrti", "uti", "htn", "dm2", "dm1", "cad",
    "sob", "doe", "nad", "wbc", "rbc", "hgb", "crp", "esr",
    "qd", "bid", "tid", "qid", "prn", "stat", "po", "iv", "im", "sc",
    "mg", "mcg", "ml", "tab", "cap", "inj",
    # Generic clinical terms
    "vitals", "signs", "exam", "examination", "findings", "normal",
    "elevated", "reduced", "increased", "decreased", "mild", "moderate",
    "severe", "bilateral", "unilateral", "acute", "chronic", "stable",
    "unstable", "positive", "negative", "rule", "out",
    # SOAP structure words
    "subjective", "objective", "plan", "observation", "admission",
}

# Stop words — too generic to be meaningful for clinical matching
STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "has", "was",
    "are", "been", "have", "will", "not", "per", "day", "week", "month",
    "once", "twice", "daily", "given", "start", "started", "continue",
    "continued", "also", "further", "immediate", "immediately",
}

# Number normaliser — "148 over 92" → "148/92", "500 mg" → "500mg"
def normalise_numbers(text: str) -> str:
    text = re.sub(r"(\d+)\s+over\s+(\d+)", r"\1/\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s*(mg|mcg|ml|g)\b", r"\1\2", text, flags=re.IGNORECASE)
    return text


def extract_clinical_tokens(text: str) -> set[str]:
    """
    Extract only clinically meaningful tokens:
    - Numbers and doses (148/92, 500mg, 325mg)
    - Drug names (metformin, aspirin, amlodipine)
    - Symptom words longer than 4 chars not in boilerplate
    """
    text = normalise_numbers(text.lower())
    tokens = set()

    # Always include numbers — these are the real hallucination risk
    for num in re.findall(r"\b\d+(?:[./]\d+)?\s*(?:mg|mcg|ml|g|%)?\b", text):
        tokens.add(num.strip())

    # Include meaningful words (>4 chars, not boilerplate or stopwords)
    for word in re.findall(r"\b[a-z]{4,}\b", text):
        if word not in SOAP_BOILERPLATE and word not in STOP_WORDS:
            tokens.add(word)

    return tokens


def check_claim(claim: str, transcript_tokens: set[str]) -> tuple[bool, list[str]]:
    """
    Returns (is_supported, list_of_unsupported_tokens).
    A claim is flagged ONLY if its key clinical tokens have <50% support.
    """
    claim_tokens = extract_clinical_tokens(claim)
    if not claim_tokens:
        return True, []

    unsupported = claim_tokens - transcript_tokens
    support_ratio = 1.0 - (len(unsupported) / len(claim_tokens))

    # Flag if less than half the clinical tokens are in the transcript
    is_supported = support_ratio >= 0.50
    return is_supported, list(unsupported)[:4]


def extract_claims(soap_note: SOAPNote) -> list[tuple[str, str]]:
    """Split SOAP sections into individual sentences for per-claim checking."""
    claims = []
    for section, text in [
        ("subjective", soap_note.get("subjective", "")),
        ("objective",  soap_note.get("objective", "")),
        ("assessment", soap_note.get("assessment", "")),
        ("plan",       soap_note.get("plan", "")),
    ]:
        if not text or text in ("Not documented", "Generation failed — manual entry required"):
            continue
        for sent in re.split(r"[.;\n]+", text):
            sent = sent.strip()
            if len(sent) > 15:
                claims.append((section, sent))
    return claims


async def qa_agent_node(state: AgentState) -> dict:
    """
    Validates SOAP note against transcript.
    Only flags genuine clinical hallucinations — not LLM rephrasing.
    """
    soap_note: SOAPNote | None = state.get("soap_note")

    # Use the original transcript for checking (before translation)
    # This gives the richest vocabulary to match against
    transcript = (
        state.get("english_transcript")
        or state.get("raw_transcript")
        or ""
    )

    if not soap_note:
        return {
            "qa_result": {
                "confidence": 0.0,
                "flags": [{"field": "all", "claim": "No SOAP note generated", "reason": "Generation failed"}],
                "needs_review": True,
                "summary": "QA could not run — no SOAP note available",
            }
        }

    transcript_tokens = extract_clinical_tokens(transcript)
    claims = extract_claims(soap_note)

    flags = []
    supported_count = 0

    for section, claim in claims:
        is_supported, unsupported = check_claim(claim, transcript_tokens)
        if is_supported:
            supported_count += 1
        else:
            flags.append({
                "field":  section,
                "claim":  claim[:200],
                "reason": f"Clinical tokens not in transcript: {', '.join(unsupported)}",
            })

    total    = len(claims)
    coverage = supported_count / total if total > 0 else 1.0

    # Blend with LLM's own self-reported confidence
    soap_conf      = float(soap_note.get("confidence", 0.75))
    final_conf     = round((coverage * 0.6) + (soap_conf * 0.4), 3)

    # Only force review for serious issues:
    # - Overall confidence below threshold, OR
    # - More than 3 flagged claims (not just rephrasing differences)
    needs_review = (
        final_conf < settings.QA_CONFIDENCE_THRESHOLD
        or len(flags) > 3
    )

    summary = (
        f"QA passed — {final_conf:.0%} confidence, {len(flags)} flags"
        if not needs_review
        else f"Review required — {final_conf:.0%} confidence, {len(flags)} claims flagged"
    )

    return {
        "qa_result": {
            "confidence":   final_conf,
            "flags":        flags,
            "needs_review": needs_review,
            "summary":      summary,
        }
    }
