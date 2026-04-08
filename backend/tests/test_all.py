"""
VaidyaScribe test suite.

Tests:
  - NER entity extraction from clinical text
  - QA hallucination detection
  - Translation agent language detection
  - SOAP note parsing
  - API endpoint smoke tests
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


# ─── NER Agent Tests ──────────────────────────────────────────────

class TestNERAgent:
    def test_extract_vitals_bp(self):
        from app.agents.ner_agent import extract_vitals
        text = "BP is 155/90 mmHg. Heart rate 95 bpm."
        vitals = extract_vitals(text)
        assert vitals.get("bp") == "155/90"
        assert vitals.get("hr") == "95"

    def test_extract_vitals_spo2(self):
        from app.agents.ner_agent import extract_vitals
        text = "SpO2 94% on room air."
        vitals = extract_vitals(text)
        assert vitals.get("spo2") == "94"

    def test_extract_vitals_temperature(self):
        from app.agents.ner_agent import extract_vitals
        text = "Temperature 38.5 C"
        vitals = extract_vitals(text)
        assert vitals.get("temp") == "38.5"

    def test_extract_medications_with_dose(self):
        from app.agents.ner_agent import extract_medications
        text = "Patient is on Furosemide 40mg daily and Metformin 500mg twice daily."

        class FakeEnt:
            def __init__(self, t, l):
                self.text = t
                self.label_ = l

        entities = []
        meds = extract_medications(text, entities)
        names = [m["name"].lower() for m in meds]
        assert any("furosemide" in n for n in names)

    def test_duration_pattern(self):
        from app.agents.ner_agent import DURATION_PATTERN
        match = DURATION_PATTERN.search("breathlessness for 3 days")
        assert match is not None
        assert "3 days" in match.group(1)

    def test_normalise_removes_stopwords(self):
        from app.agents.qa_agent import normalise
        words = normalise("the patient has been reported with chest pain")
        assert "chest" in words
        assert "pain" in words
        assert "the" not in words
        assert "has" not in words

    def test_full_entity_extraction_smoke(self):
        from app.agents.ner_agent import extract_entities_from_text
        text = (
            "58M presenting with breathlessness for 3 days. "
            "BP 155/90. HR 98. On Furosemide 40mg daily."
        )
        result = extract_entities_from_text(text)
        assert "chief_complaint" in result
        assert "vitals" in result
        assert result["vitals"].get("bp") == "155/90"


# ─── QA Agent Tests ───────────────────────────────────────────────

class TestQAAgent:
    @pytest.mark.asyncio
    async def test_qa_passes_for_supported_note(self):
        from app.agents.qa_agent import qa_agent_node
        state = {
            "english_transcript": (
                "Patient has breathlessness and swollen feet. "
                "Blood pressure is 155 over 90. Plan to increase Furosemide."
            ),
            "soap_note": {
                "subjective": "Breathlessness and pedal oedema",
                "objective": "BP 155/90",
                "assessment": "Heart failure",
                "plan": "Increase Furosemide",
                "icd10_codes": [],
                "confidence": 0.90,
            },
        }
        result = await qa_agent_node(state)
        qa = result["qa_result"]
        assert "confidence" in qa
        assert "flags" in qa
        assert isinstance(qa["needs_review"], bool)

    @pytest.mark.asyncio
    async def test_qa_flags_hallucinated_claim(self):
        from app.agents.qa_agent import qa_agent_node
        state = {
            "english_transcript": "Patient has a headache.",
            "soap_note": {
                "subjective": "Headache",
                "objective": "Chest X-ray shows cardiomegaly with bilateral pleural effusions",
                "assessment": "Heart failure",
                "plan": "Diuretics",
                "icd10_codes": [],
                "confidence": 0.6,
            },
        }
        result = await qa_agent_node(state)
        qa = result["qa_result"]
        # "cardiomegaly" and "pleural effusions" are not in the transcript
        assert qa["needs_review"] is True
        assert len(qa["flags"]) > 0

    @pytest.mark.asyncio
    async def test_qa_handles_missing_soap(self):
        from app.agents.qa_agent import qa_agent_node
        state = {"soap_note": None, "english_transcript": "some text"}
        result = await qa_agent_node(state)
        assert result["qa_result"]["needs_review"] is True

    def test_check_claim_in_transcript_positive(self):
        from app.agents.qa_agent import check_claim_in_transcript, normalise
        transcript_words = normalise("patient has breathlessness and elevated blood pressure")
        supported, unsupported = check_claim_in_transcript("breathlessness and hypertension", transcript_words)
        assert supported is True

    def test_check_claim_in_transcript_negative(self):
        from app.agents.qa_agent import check_claim_in_transcript, normalise
        transcript_words = normalise("patient has a simple headache today")
        supported, unsupported = check_claim_in_transcript(
            "pulmonary embolism with bilateral deep vein thrombosis confirmed", transcript_words
        )
        assert supported is False
        assert len(unsupported) > 0


# ─── SOAP Parser Tests ────────────────────────────────────────────

class TestSOAPParser:
    def test_parse_valid_json(self):
        from app.agents.soap_generator import parse_soap_response
        import json
        payload = json.dumps({
            "subjective": "Patient has headache",
            "objective": "BP 148/92",
            "assessment": "Hypertension",
            "plan": "Start Amlodipine 5mg",
            "icd10_codes": ["I10"],
            "confidence": 0.88,
        })
        result = parse_soap_response(payload)
        assert result["subjective"] == "Patient has headache"
        assert result["icd10_codes"] == ["I10"]
        assert result["confidence"] == 0.88

    def test_parse_json_with_markdown_fences(self):
        from app.agents.soap_generator import parse_soap_response
        payload = """```json
{"subjective":"Headache","objective":"Normal","assessment":"URTI","plan":"Rest","icd10_codes":[],"confidence":0.7}
```"""
        result = parse_soap_response(payload)
        assert result["subjective"] == "Headache"

    def test_parse_malformed_returns_graceful_fallback(self):
        from app.agents.soap_generator import parse_soap_response
        result = parse_soap_response("This is not valid JSON at all")
        assert result["confidence"] == 0.3
        assert "manual review" in result["assessment"].lower()


# ─── Language Detection Tests ─────────────────────────────────────

class TestLanguageDetection:
    def test_detect_mixed_language(self):
        from app.agents.stt_agent import detect_language_mix, TranscriptSegment
        segments: list[TranscriptSegment] = [
            {"text": "patient-ku breathlessness irukku", "lang": "ta", "confidence": 0.9, "start_time": 0, "end_time": 2},
            {"text": "blood pressure is 155 over 90", "lang": "en", "confidence": 0.95, "start_time": 2, "end_time": 5},
        ]
        assert detect_language_mix(segments) == "tamil-english"

    def test_detect_english_only(self):
        from app.agents.stt_agent import detect_language_mix, TranscriptSegment
        segments: list[TranscriptSegment] = [
            {"text": "patient has a headache", "lang": "en", "confidence": 0.95, "start_time": 0, "end_time": 3},
        ]
        assert detect_language_mix(segments) == "english"

    def test_detect_tamil_only(self):
        from app.agents.stt_agent import detect_language_mix, TranscriptSegment
        segments: list[TranscriptSegment] = [
            {"text": "thalai valikkuthu", "lang": "ta", "confidence": 0.88, "start_time": 0, "end_time": 2},
        ]
        assert detect_language_mix(segments) == "tamil"


# ─── Supervisor Routing Tests ─────────────────────────────────────

class TestSupervisorRouting:
    def test_routes_to_human_review_on_flags(self):
        from app.agents.supervisor import route_from_supervisor
        state = {"next_step": "human_review"}
        assert route_from_supervisor(state) == "human_review"

    def test_routes_to_auto_approve_on_clean_qa(self):
        from app.agents.supervisor import route_from_supervisor
        state = {"next_step": "auto_approve"}
        assert route_from_supervisor(state) == "auto_approve"

    def test_defaults_to_human_review(self):
        from app.agents.supervisor import route_from_supervisor
        state = {"next_step": None}
        assert route_from_supervisor(state) == "human_review"


# ─── API Smoke Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_consent_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sessions/consent", json={
            "doctor_id": "DR-TEST-001",
            "patient_id": "PT-TEST-001",
            "consent_given": True,
        })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["consent_given"] is True


@pytest.mark.asyncio
async def test_note_not_found_returns_404():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/notes/nonexistent-session-id")
    assert response.status_code == 404
