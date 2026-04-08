"""
NER Agent — Medical Named Entity Recognition using scispaCy.

Uses en_core_sci_md (free, offline pre-trained medical model).
Extracts: symptoms, medications, vitals, ICD-10 codes, allergies, plan.

ICD-10 mapping uses a lightweight offline CSV lookup
(download: https://raw.githubusercontent.com/k4m1113/ICD-10-CSV/master/codes.csv)
"""
from __future__ import annotations
import re
import csv
import os
import asyncio
from pathlib import Path
from app.agents.state import AgentState, ExtractedEntities

_nlp = None
_icd10_map: dict[str, str] = {}


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_sci_md")
        except OSError:
            # Fallback to basic English model if scispaCy not downloaded
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


def load_icd10_map():
    global _icd10_map
    if _icd10_map:
        return _icd10_map
    icd_path = Path("data/icd10_codes.csv")
    if icd_path.exists():
        with open(icd_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("code", row.get("Code", "")).strip()
                desc = row.get("description", row.get("Description", "")).strip().lower()
                if code and desc:
                    _icd10_map[desc] = code
    return _icd10_map


# ─── Vital signs pattern extraction ──────────────────────────────

VITALS_PATTERNS = {
    "bp": re.compile(r"(?:BP|blood pressure)[:\s]*(\d{2,3})[/\\](\d{2,3})", re.IGNORECASE),
    "hr": re.compile(r"(?:HR|heart rate|pulse)[:\s]*(\d{2,3})", re.IGNORECASE),
    "temp": re.compile(r"(?:temp(?:erature)?)[:\s]*(\d{2,3}(?:\.\d)?)\s*(?:°?[CF])?", re.IGNORECASE),
    "spo2": re.compile(r"(?:SpO2|oxygen saturation)[:\s]*(\d{2,3})\s*%?", re.IGNORECASE),
    "weight": re.compile(r"(?:weight|wt)[:\s]*(\d{2,3}(?:\.\d)?)\s*(?:kg|lbs?)?", re.IGNORECASE),
    "rr": re.compile(r"(?:RR|respiratory rate)[:\s]*(\d{1,2})", re.IGNORECASE),
}

MED_DOSE_PATTERN = re.compile(
    r"(\w[\w\s-]+?)\s+(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|units?)\s*"
    r"(?:(once|twice|thrice|\d+\s*times?)\s*(?:a\s*)?(?:daily|day|week)?)?",
    re.IGNORECASE
)

DURATION_PATTERN = re.compile(
    r"(?:for|since|over|past)\s+(\d+\s+(?:day|week|month|year)s?)",
    re.IGNORECASE
)


def extract_vitals(text: str) -> dict:
    vitals = {}
    for key, pattern in VITALS_PATTERNS.items():
        match = pattern.search(text)
        if match:
            if key == "bp":
                vitals[key] = f"{match.group(1)}/{match.group(2)}"
            else:
                vitals[key] = match.group(1)
    return vitals


def extract_medications(text: str, entities) -> list[dict]:
    meds = []
    # From NER entities labelled as CHEMICAL or DRUG
    ner_meds = {ent.text.lower() for ent in entities if ent.label_ in ("CHEMICAL", "DRUG", "MEDICATION")}
    for med in ner_meds:
        meds.append({"name": med, "dose": None, "frequency": None})

    # From regex patterns (more precise)
    for match in MED_DOSE_PATTERN.finditer(text):
        name = match.group(1).strip().lower()
        if len(name) > 2:  # filter noise
            meds.append({
                "name": name,
                "dose": f"{match.group(2)}{match.group(3)}",
                "frequency": match.group(4) if match.lastindex >= 4 else None,
            })

    # Deduplicate by name
    seen = set()
    unique_meds = []
    for m in meds:
        if m["name"] not in seen:
            seen.add(m["name"])
            unique_meds.append(m)
    return unique_meds


def map_to_icd10(symptoms: list[str]) -> list[str]:
    """Lightweight offline ICD-10 mapping based on symptom keywords."""
    icd_map = load_icd10_map()
    codes = []
    for symptom in symptoms[:5]:  # limit to top 5
        symptom_lower = symptom.lower()
        for desc, code in icd_map.items():
            if any(word in desc for word in symptom_lower.split() if len(word) > 3):
                codes.append(code)
                break
    return list(set(codes))


def extract_entities_from_text(text: str) -> ExtractedEntities:
    nlp = get_nlp()
    doc = nlp(text)

    # Extract named entities
    symptoms = [ent.text for ent in doc.ents if ent.label_ in ("DISEASE", "SIGN_OR_SYMPTOM", "SYMPTOM")]
    medications = extract_medications(text, doc.ents)
    vitals = extract_vitals(text)

    # Chief complaint — first sentence or symptom mention
    sents = list(doc.sents)
    chief_complaint = sents[0].text.strip() if sents else text[:200]

    # Duration
    duration_match = DURATION_PATTERN.search(text)
    duration = duration_match.group(1) if duration_match else ""

    # Allergies
    allergy_pattern = re.compile(r"(?:allergic|allergy|NKDA|no known drug)[:\s]*([\w\s,]+?)(?:\.|,|;|\n)", re.IGNORECASE)
    allergy_match = allergy_pattern.search(text)
    allergies = [allergy_match.group(1).strip()] if allergy_match else []

    # Plan keywords
    plan_pattern = re.compile(r"(?:plan|prescri|recommend|start|continue|refer)[\w\s:,]+?(?:\.|$)", re.IGNORECASE | re.MULTILINE)
    plan_keywords = [m.group().strip() for m in plan_pattern.finditer(text)][:5]

    # ICD-10 codes
    icd10_codes = map_to_icd10(symptoms)

    return {
        "chief_complaint": chief_complaint,
        "symptoms": list(set(symptoms))[:10],
        "duration": duration,
        "medications": medications,
        "vitals": vitals,
        "allergies": allergies,
        "icd10_codes": icd10_codes,
        "plan_keywords": plan_keywords,
    }


async def ner_agent_node(state: AgentState) -> dict:
    """Runs scispaCy NER on the English transcript to extract clinical entities."""
    transcript = state.get("english_transcript") or state.get("raw_transcript", "")

    if not transcript:
        return {"entities": None}

    entities = await asyncio.to_thread(extract_entities_from_text, transcript)
    return {"entities": entities}
