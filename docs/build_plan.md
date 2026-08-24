# ADDT Build Plan and Task Checklist

Companion to `addt_solution_design.md`. This file tracks implementation progress. Checkboxes are marked done as each task is completed. Not a design document — if anything here conflicts with `addt_solution_design.md`, the solution design wins.

## Technical decisions locked in

- **Layout**: single monorepo — `/backend` (FastAPI), `/frontend` (React/Vite/TS), `/docs`, `docker-compose.yml`.
- **DB**: local PostgreSQL + pgvector via Docker Compose.
- **Backend tooling**: `uv` for env/deps, pytest, ruff. 
- **Frontend tooling**: Vite + TypeScript, Vitest.
- **Synthetic data**: Claude drafts the fake patient records and the 10–20 case synthetic set; user reviews/corrects before anything downstream relies on it.
- **GPU**: user already has an arrangement (details TBD). Since the QLoRA fine-tune needs clinician data anyway, no provisioning work now — just leave a config seam for it in Phase 2.
- **Constraint checker**: declarative rules as YAML/JSON (condition → red-flag action), evaluated by a hand-rolled Python engine — not a third-party rules library. Matches Section 8's "deterministic, not probabilistic" requirement.
- **Knowledge graph (Layer 3.2)**: modeled as edge tables inside the same Postgres DB rather than a separate graph database (e.g. Neo4j). Matches Section 8's "one database, simple for a one person build" reasoning.

---

## Phase 1 — Data Twin

- [x] 1. Repo scaffold: monorepo structure, `docker-compose.yml` (Postgres+pgvector), backend `pyproject.toml` (uv), frontend Vite+TS scaffold, ruff/pytest/vitest wired, `.gitignore`, `git init`.
- [x] 2. DB schema from Section 7 as SQLAlchemy models + Alembic migrations — every table, `clinician_id` on all of them (except `guideline_documents`/`guideline_chunks`, which the printed Section 7 schema deliberately omits it from, since guideline corpus is shared across tenants), pgvector columns on `guideline_chunks.embedding` and `case_precedent_vectors.embedding`. Seed script with synthetic dummy rows across ≥2 fake `clinician_id`s to prove tenant isolation early; covered by an automated test.
- [x] 3. Source the Nigeria STG and WHO primary care documents (public), then build the guideline ingestion pipeline: PDF parse → chunk → BGE-M3 embed → `guideline_documents`/`guideline_chunks`, plus the relation-extraction step that populates the graph edge tables. **Gap:** full-corpus BGE-M3 embedding has not been run yet (verified via a real smoke test instead — see `docs/setup.md`); both documents are ingested with `--no-embed` (chunks + graph nodes/edges populated, `embedding = NULL`). Also unresolved: the Nigeria STG PDF's edition is unverified (see `docs/guideline_corpus/README.md`).
- [x] 4. De-identification pipeline: rules to strip identifying fields, tested against synthetic fake patient records. `backend/src/backend/deidentify.py` — deterministic regex-based redaction (name via title+capitalized heuristic, phone, email, national ID, date, address) plus a pseudonymous `patient_ref` generator decoupled from any PII. Validated against the real 652-chunk STG corpus: zero false positives on clinical content outside expected front-matter hits (contributor names, ministry address). Known limitation, documented in the module: title-less names aren't caught — this is a redaction aid, not a substitute for the console's human review step.
- [x] 5. Synthetic case set: 10–20 primary care cases spanning the three disposition classes, for elicitation-session prep and as the baseline agent's test set. **⚠ Claude-drafted, not yet clinician-reviewed** — `backend/src/backend/fixtures/synthetic_cases.yaml`, 15 cases (5 per class), each grounded in a real condition label already extracted from the ingested STG corpus (verified to match `guideline_graph_nodes` exactly). Loader validates schema (`backend/src/backend/fixtures/loader.py`), covered by tests. **Also newly decided here** (the design doc never names the three disposition classes): `manage_at_primary_care` / `refer_routine` / `refer_urgent_emergency`, defined in `backend/src/backend/disposition.py`, severity-ordered for Section 10's severity-weighted error matrix. Retrofitted into `seed.py`'s placeholder dispositions, which were never a real decision.
- [x] 6. Layer 2 ingestion API: upload endpoint with retry + local queuing for consultation transcripts — testable end-to-end with dummy payloads, no real audio/patient data required. **Scope boundary, stated explicitly:** "local queuing" in Section 5.2's sense is a client-side responsibility that belongs to the console (Layer 8, task 11, not yet built). Built the server-side half: `POST /ingestion/transcripts` (`backend/src/backend/api/ingestion.py`) is idempotent per `(clinician_id, idempotency_key)` — a retried upload with the same key+content returns the original result (200, not a duplicate), same key with different content returns 409, unknown `clinician_id` returns 404. Backed by a new `ingestion_queue` table (not in Section 7's printed schema, same situation as the graph tables in task 3 — a raw upload isn't yet a processed `consultations` row per Section 6.1, that's Layer 7.1's job, not yet built).

  **Updated after a self-review (`docs/security_review.md`):** the first version of this endpoint had no auth, never called the task 4 de-identification module, never checked `consent_status`, and wrote no audit trail — the modules existed but weren't wired to the one API that used them. Fixed: a shared service API key (`backend/src/backend/api/auth.py`, `X-Service-Api-Key` header, 401 if missing/wrong — single shared key, not per-clinician, since Layer 8 has no login system yet); `content` is now de-identified before storage, with only a category-count `redaction_summary` persisted, never the redacted values; upload is rejected with 403 unless `clinicians.consent_status == "granted"`; every accepted upload (including idempotent replays) writes an `audit_log` row. New `ingestion_queue.redaction_summary` (JSONB) column/migration. 11 integration tests now (was 6), all passing against the real DB, including the new auth/consent/redaction/audit-log cases.
- [x] 7. Push-to-record UI control + Whisper/MMS transcription pipeline scaffold (Section 6.1), tested against non-patient sample audio. Code path only — not switched on for real consultations until ethics clearance.
  - Frontend: `frontend/src/components/PushToRecordButton.tsx` — explicit start/stop via `MediaRecorder` (no passive listening, per Section 6.1). Deliberately not wired into a console page yet (that composition belongs to task 11, not yet built); tested standalone (4 tests, mocking `getUserMedia`/`MediaRecorder`).
  - Backend: `backend/src/backend/transcription/whisper_backend.py`, using `faster-whisper` rather than the original `openai-whisper` package — this dev environment has no system `ffmpeg`, which `openai-whisper` requires unconditionally; `faster-whisper` decodes via PyAV, whose wheel bundles its own FFmpeg libraries. `MODEL_SIZE = "base"` is a scaffold choice for a fast smoke test, not a Nigerian-language accuracy evaluation — that needs real audio, still gated behind ethics clearance. Real smoke test (downloads the model for real, opt-in like the embedding smoke test) transcribes a synthetic, non-patient TTS-generated WAV fixture (`backend/tests/fixtures/sample_audio.wav`, provenance in that folder's `README.md`) and passes.
  - Whisper vs. MMS, and final model size, remain open — revisit once real consultation audio exists to evaluate against.

## Phase 2 — Model Twin

- [ ] 8. Constraint checker: rule set compiled from the public guideline corpus, unit tested including cases designed to trip red flags.
- [ ] 9. Guideline-only baseline agent: Layer 4 guideline grounding + Layer 7 orchestrator, no persona policy, minimal ReAct loop (perceive → retrieve → draft → check → explain → escalate), run against the synthetic case set from task 5.

## Phase 3 — Agent Twin

- [ ] 10. Full service layer (6.1–6.5): Connector class, data services scoped by `clinician_id`+consent, AI/ML service calling the baseline agent, XAI service (explanation object for guideline-only output), cognitive services (perceive/reason/act) — tested against dummy tenants.
- [ ] 11. Console shell, both views (intake/case, review queue/dashboard), built against mock data from the service layer stubs.

---

## Tasks strictly dependent on the clinician and real data

Not implementation work Claude can do independently — tracked here so progress against Section 11 stays visible in one place. Each needs the doctor confirmed, consented, and (marked ⚠) ethics clearance.

- [ ] Ingest the doctor's real standing protocols (needs doctor confirmed + consented).
- [ ] Elicitation session transcripts — the doctor working through cases; primary real training signal for Phase 1.
- [ ] ⚠ Retrospective real consultation records (needs clinician consent *and* ethics clearance — patient data).
- [ ] Persona policy QLoRA fine-tune (needs elicitation/consultation data above).
- [ ] Precedent memory population with real case vectors.
- [ ] Full-twin vs. baseline offline evaluation (Section 10 metrics: concordance, kappa, severity-weighted errors).
- [ ] Wire console/service layer to the real persona policy + precedent memory.
- [ ] ⚠ Shadow deployment — learning mode on real consultations (doctor + per-consultation patient consent + ethics clearance for audio capture).
- [ ] Consulting-mode sandbox evaluation on held-out real cases.
