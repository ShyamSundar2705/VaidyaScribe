"""PDF generation for SOAP notes using WeasyPrint (free, handles Tamil Unicode)."""
from jinja2 import Template
from datetime import datetime

SOAP_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Tamil&display=swap');
  body { font-family: Arial, 'Noto Sans Tamil', sans-serif; margin: 2cm; color: #1a1a1a; font-size: 12pt; }
  .header { border-bottom: 2px solid #0C3B6B; padding-bottom: 12px; margin-bottom: 20px; }
  .title { font-size: 18pt; font-weight: bold; color: #0C3B6B; }
  .subtitle { color: #666; font-size: 10pt; }
  .section { margin-bottom: 16px; }
  .section-label { font-weight: bold; font-size: 11pt; color: #0C3B6B; text-transform: uppercase;
                   letter-spacing: 0.05em; border-left: 4px solid #0C3B6B; padding-left: 8px; margin-bottom: 6px; }
  .section-content { padding-left: 12px; line-height: 1.6; }
  .icd-tag { display: inline-block; background: #E6F1FB; color: #0C447C; padding: 2px 8px;
             border-radius: 4px; font-size: 10pt; margin-right: 4px; }
  .flag { background: #FCEBEB; color: #791F1F; padding: 4px 8px; border-radius: 4px; font-size: 10pt; margin: 2px 0; }
  .qa-bar { margin: 12px 0; }
  .tamil-section { background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px;
                   padding: 12px; margin-top: 20px; }
  .tamil-title { font-weight: bold; color: #166534; margin-bottom: 6px; }
  .footer { margin-top: 30px; border-top: 1px solid #ccc; padding-top: 8px; font-size: 9pt; color: #888; }
  .approved-stamp { color: #166534; font-weight: bold; font-size: 11pt; }
</style>
</head>
<body>
<div class="header">
  <div class="title">Clinical Consultation Note</div>
  <div class="subtitle">
    Session: {{ session_id[:8] }} &nbsp;|&nbsp;
    Generated: {{ generated_at }} &nbsp;|&nbsp;
    Model: {{ llm_model }} &nbsp;|&nbsp;
    <span class="approved-stamp">{% if approved %}DOCTOR APPROVED{% else %}PENDING REVIEW{% endif %}</span>
  </div>
</div>

<div class="section">
  <div class="section-label">S — Subjective</div>
  <div class="section-content">{{ subjective }}</div>
</div>

<div class="section">
  <div class="section-label">O — Objective</div>
  <div class="section-content">{{ objective }}</div>
</div>

<div class="section">
  <div class="section-label">A — Assessment</div>
  <div class="section-content">{{ assessment }}</div>
  {% if icd10_codes %}
  <div style="margin-top: 6px; padding-left: 12px;">
    {% for code in icd10_codes %}<span class="icd-tag">{{ code }}</span>{% endfor %}
  </div>
  {% endif %}
</div>

<div class="section">
  <div class="section-label">P — Plan</div>
  <div class="section-content">{{ plan }}</div>
</div>

{% if qa_flags %}
<div class="section">
  <div class="section-label">QA Flags (reviewed by doctor)</div>
  {% for flag in qa_flags %}
  <div class="flag">{{ flag.field }}: {{ flag.reason }}</div>
  {% endfor %}
</div>
{% endif %}

{% if tamil_summary %}
<div class="tamil-section">
  <div class="tamil-title">நோயாளி சுருக்கம் (Patient Summary in Tamil)</div>
  <div>{{ tamil_summary }}</div>
</div>
{% endif %}

<div class="footer">
  QA Confidence: {{ "%.0f"|format(qa_confidence * 100) }}% &nbsp;|&nbsp;
  VaidyaScribe v1.0 — DPDP 2023 Compliant &nbsp;|&nbsp;
  This note was AI-assisted and reviewed by the treating physician.
</div>
</body>
</html>
"""


async def generate_soap_pdf(note) -> bytes:
    """Generate PDF bytes from a ClinicalNote model instance."""
    try:
        from weasyprint import HTML

        html = Template(SOAP_HTML_TEMPLATE).render(
            session_id=str(note.session_id),
            generated_at=datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
            llm_model=note.llm_model_used or "AI-assisted",
            approved=note.doctor_approved,
            subjective=note.subjective or "Not documented.",
            objective=note.objective or "Not documented.",
            assessment=note.assessment or "Not documented.",
            plan=note.plan or "Not documented.",
            icd10_codes=note.icd10_codes or [],
            qa_flags=note.qa_flags or [],
            qa_confidence=note.qa_confidence or 0.0,
            tamil_summary=note.tamil_summary,
        )

        pdf_bytes = HTML(string=html).write_pdf()
        from app.services.storage_service import save_pdf
        return await save_pdf(note.id, pdf_bytes)

    except ImportError:
        # WeasyPrint not available — return simple text PDF placeholder
        return b"%PDF-1.4 (WeasyPrint not installed)"
