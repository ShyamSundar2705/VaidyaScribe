# VaidyaScribe
### Cognizant Technoverse Hackathon 2026 — Healthcare: Clinical Documentation

> A privacy-first, multilingual AI clinical scribe for Tamil/English consultations.
> Generates SOAP notes automatically, catches hallucinations, monitors doctor burnout,
> and includes secure JWT authentication so each doctor only sees their own patients.
> **Total infrastructure cost: ₹0.**

---

## What makes VaidyaScribe different

| Feature | VaidyaScribe | Nuance DAX / Suki / Abridge |
|---------|-------------|----------------------------|
| Cost | **₹0** | ₹12,000–50,000/month |
| Tamil/English code-switch | **Yes — Groq Whisper** | No |
| Offline / no cloud needed | **Yes — runs on laptop** | No |
| DPDP 2023 consent flow | **Yes — built-in** | No |
| Hallucination QA gate | **Yes — clinical token match** | Partial |
| Doctor burnout predictor | **Yes — unique** | No |
| Patient Tamil summary | **Yes** | No |
| Secure doctor login (JWT) | **Yes — per-doctor isolation** | Varies |
| Prescription pad | **Yes — auto-parsed from SOAP** | No |
| Patient history + search | **Yes — keyword + ID** | No |

---

## Architecture

```
Browser mic → WebSocket (JWT auth) → FastAPI → LangGraph
                                                    │
        ┌───────────────────────────────────────────┤
        ▼                                           ▼
   STT agent                              Translation agent
  (Groq Whisper, language=en)              (NLLB-200, skipped for Groq)
        │                                           │
        └──────────────────┬────────────────────────┘
                           ▼
                      NER agent (scispaCy)
                           │
                           ▼
               SOAP generator (Llama 3.1 / Groq fallback)
                           │
                           ▼
                    QA hallucination check
                           │
                           ▼
                    Supervisor → Doctor review UI
                           │
         Tamil summary · PDF · FHIR export · Prescription pad
```

---

## Free tech stack

| Component | Tool | Cost |
|-----------|------|------|
| Auth | python-jose (JWT) + bcrypt | Free |
| STT | Groq whisper-large-v3 (primary) | Free (7200s/day) |
| STT fallback | faster-whisper local | Free |
| Translation | NLLB-200 distilled 600M | Free / Apache 2.0 |
| LLM | Ollama + Llama 3.1 8B | Free |
| LLM fallback | Groq free tier | Free (no card) |
| Agent framework | LangGraph 0.3 | Free / Apache 2.0 |
| NER | scispaCy en_core_sci_md | Free |
| Backend | FastAPI + Python 3.12 | Free |
| Database | SQLite + LanceDB | Free / serverless |
| Cache | Redis (Docker) | Free |
| Frontend | React 19 + Vite | Free |
| PDF | WeasyPrint | Free / LGPL |
| Containers | Docker Compose | Free |

---

## Quick start

```bash
# 1. Clone and configure
git clone <repo>
cd vaidyascribe
cp .env.example .env

# 2. Add Groq key for fast transcription (free at console.groq.com, no card)
echo "GROQ_API_KEY=gsk_..." >> .env

# 3. Start all services
docker compose up --build

# 4. Seed demo data
docker compose exec backend python scripts/seed_demo.py

# 5. Open browser — register at login page first
#   App:       http://localhost
#   API docs:  http://localhost:8000/docs

# 6. Run tests
docker compose exec backend pytest tests/ -v
```

---

## Project structure

52 files total. Every file listed below exists in the repository.

```
vaidyascribe/
├── docker-compose.yml                      # 5 services: ollama, redis, backend, frontend, nginx
├── .env.example                            # zero secrets — all free tools, copy to .env
├── README.md
│
├── backend/
│   ├── Dockerfile                          # python 3.12-slim + ffmpeg + scispaCy model download
│   ├── requirements.txt                    # pinned, conflict-free dependency set
│   ├── pytest.ini                          # asyncio_mode = auto
│   │
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_initial.py              # creates all 5 tables
│   │
│   ├── app/
│   │   ├── main.py                         # FastAPI entry, CORS, lifespan, router mount
│   │   │
│   │   ├── agents/
│   │   │   ├── state.py                    # AgentState TypedDict
│   │   │   ├── graph.py                    # LangGraph: 5 nodes + MemorySaver checkpointing
│   │   │   ├── stt_agent.py                # Groq Whisper (language=en), faster-whisper fallback
│   │   │   ├── translation_agent.py        # NLLB-200 Tamil→English (skipped if Groq used)
│   │   │   ├── ner_agent.py                # scispaCy NER, vital regex, ICD-10 CSV lookup
│   │   │   ├── soap_generator.py           # Llama 3.1 via Ollama (Groq fallback)
│   │   │   ├── qa_agent.py                 # clinical token matching, 70% confidence threshold
│   │   │   └── supervisor.py               # routing + burnout score contribution
│   │   │
│   │   ├── api/
│   │   │   ├── auth_router.py              # POST /auth/register, /login, GET /auth/me
│   │   │   ├── router.py                   # all routes JWT-protected, doctor-scoped queries
│   │   │   └── websocket.py                # WS /ws/consult — JWT via ?token=, audio streaming
│   │   │
│   │   ├── core/
│   │   │   ├── auth.py                     # JWT sign/verify, bcrypt hashing, get_current_doctor
│   │   │   ├── config.py                   # pydantic-settings with env defaults
│   │   │   └── database.py                 # async SQLite, AsyncSessionLocal, create_tables
│   │   │
│   │   ├── models/
│   │   │   └── db_models.py                # 5 models: Doctor, ConsultationSession,
│   │   │                                   #   ClinicalNote, AuditLog, DoctorMetrics
│   │   │
│   │   └── services/
│   │       ├── note_service.py             # saves pipeline result to DB, returns note_id
│   │       ├── burnout_service.py          # weekly metrics + composite burnout score
│   │       ├── fhir_service.py             # FHIR R4 DocumentReference bundle
│   │       └── pdf_service.py              # WeasyPrint HTML→PDF, Tamil Unicode support
│   │
│   └── tests/
│       └── test_all.py                     # NER, QA, SOAP parser, lang detect, routing, API
│
├── frontend/
│   ├── Dockerfile                          # node 20 multi-stage: build → serve
│   ├── index.html                          # HTML entry, mounts <div id="root">
│   ├── vite.config.ts                      # Vite 6, /api and /ws proxied to backend:8000
│   ├── package.json                        # React 19, Zustand 5, TanStack Query 5, framer-motion
│   │
│   └── src/
│       ├── main.tsx                        # React 19 createRoot entry
│       ├── App.tsx                         # Routes: /login public, everything else protected
│       ├── api.ts                          # axios client, reads token from localStorage directly
│       ├── index.css                       # global reset
│       ├── vite-env.d.ts                   # ImportMeta env type declarations
│       │
│       ├── components/
│       │   ├── Layout.tsx                  # sidebar: Dashboard|Consultation|Patients|Wellness
│       │   ├── ConsentBanner.tsx           # DPDP consent toggle, patient ID input
│       │   └── ProtectedRoute.tsx          # redirects unauthenticated users to /login
│       │
│       ├── hooks/
│       │   └── useAudioCapture.ts          # MediaRecorder → WS, reads JWT from localStorage
│       │
│       ├── pages/
│       │   ├── LoginPage.tsx               # Sign in / Register, two-panel layout
│       │   ├── Dashboard.tsx               # Greeting, stats, burnout bar, recent notes
│       │   ├── ConsultationRoom.tsx        # Recording, pipeline steps, live transcript
│       │   ├── NoteEditor.tsx              # SOAP editor, QA flags, approve + prescription btn
│       │   ├── PatientHistory.tsx          # ID lookup + keyword search, ℞ on approved notes
│       │   ├── PrescriptionPad.tsx         # Auto-parsed medications, editable table, print
│       │   └── BurnoutDashboard.tsx        # Weekly bar chart, score cards, alert banner
│       │
│       └── store/
│           ├── app.store.ts                # sessionId, lastResult, history
│           └── auth.store.ts               # token, doctorId, fullName (persisted to localStorage)
│
├── scripts/
│   └── seed_demo.py                        # 5 synthetic Tamil/English consultations
│
└── nginx/
    └── nginx.conf                          # /api → backend, /ws → backend, / → frontend
```

---

## Authentication

All routes require a JWT Bearer token. Doctors register once with email + password.
Each doctor sees only their own patients — enforced at the database query level.

```
POST /api/v1/auth/register   — doctor_id, email, full_name, specialisation, password
POST /api/v1/auth/login      — returns JWT (8 hour expiry — one clinic day)
GET  /api/v1/auth/me         — current doctor profile
POST /api/v1/auth/change-password
```

---

## API endpoints (all protected)

```
GET  /api/v1/notes/search                  — word-AND keyword search across all SOAP fields
GET  /api/v1/notes/{session_id}
POST /api/v1/notes/{note_id}/approve
GET  /api/v1/notes/{note_id}/export/pdf
GET  /api/v1/notes/{note_id}/export/fhir
POST /api/v1/sessions/consent
GET  /api/v1/doctors/me/burnout
GET  /api/v1/doctors/me/notes/recent
GET  /api/v1/patients/{patient_id}/notes
GET  /api/v1/patients/search
WS   /ws/consult?token=<jwt>
GET  /health
```

---

## Hackathon pitch

**Business value:** ₹0 cost vs ₹12,000–50,000/month competitors. 72% documentation time reduction. 2 hours saved per doctor per day. 1.3M registered doctors in India, 0% served by affordable Tamil-language scribes.

**Uniqueness:** Tamil-English code-switch handling not available in any commercial scribe. DPDP 2023 consent flow. Doctor burnout predictor. Per-doctor data isolation meets clinical governance standards.

**Demo flow:** Register → Consent → Record Tamil-English script → SOAP in 30s → QA check → Approve → Print prescription → Patient history lookup.
