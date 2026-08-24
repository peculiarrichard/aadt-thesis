# Phase 1 Gap and Security Review

Self-review of `docs/build_plan.md` tasks 1-7, done by re-reading the actual code (not from memory) on 2026-08-24. Organized by severity. **Items 1-4 fixed same day** (see each item); items 5-14 are documented, not yet fixed — deferred per user decision, revisit before this goes beyond a local single-clinician pilot.

## Critical — undermined the design's own multi-tenancy/privacy guarantees

1. **FIXED. No authentication or authorization on the ingestion API.** `POST /ingestion/transcripts` and `GET /ingestion/transcripts` (`backend/src/backend/api/ingestion.py`) accepted any `clinician_id` with no verification that the caller is that clinician or acting on their behalf. — Added a shared service API key (`backend/src/backend/api/auth.py`, `require_service_api_key`), required via `X-Service-Api-Key` header on every route in the router (`dependencies=[...]` at router level), 401 if missing/wrong. This authenticates "trusted intake tooling," not a specific clinician — there's still no per-clinician identity check, since Layer 8 (console, real login) doesn't exist yet. Revisit when it does.

2. **FIXED. De-identification (task 4) was built but never called.** `backend/src/backend/deidentify.py` existed, was tested, and worked — but nothing in the ingestion API called `deidentify_text()`. — `upload_transcript()` now calls it before any comparison or storage; `ingestion_queue.content` only ever holds de-identified text. Added `ingestion_queue.redaction_summary` (JSONB, new migration) storing only category counts (e.g. `{"PHONE": 1}`), never the redacted values — inspectable without being a second copy of the PII it describes. Returned in the API response too.

3. **FIXED. Consent status was never checked.** Section 5.6.2: "Data services: read and write access to Layer 3, scoped by clinician_id **and by consent status**." — `upload_transcript()` now rejects with 403 unless `clinician.consent_status == "granted"` (this project's own convention for the value, since Section 7 doesn't define an enum for this free-text column — documented in the code).

4. **FIXED. No audit trail.** `audit_log` existed in the schema specifically for this, but only `seed.py`'s dummy data ever wrote to it. — Every accepted upload, including idempotent replays, now writes an `AuditLog` row (`actor=SYSTEM`, `action="ingestion_upload"` or `"ingestion_upload_replay"`, `reference_table="ingestion_queue"`, `reference_id=<ingestion_id>`).

Verification: 5 new integration tests (401 missing key, 401 wrong key, 403 unconsented clinician, redaction verified against the stored row, audit_log row verified) plus the original 6, all 11 passing against the real DB. See `backend/tests/test_ingestion_api.py`.

## High — real risk, smaller blast radius right now

5. **Postgres port bound to all interfaces.** `docker-compose.yml`'s `ports: ["${POSTGRES_PORT:-5432}:5432"]` binds to `0.0.0.0`, not `127.0.0.1`. On a dev machine attached to any network, the DB is reachable from other hosts on that network using the well-known default dev password.

6. **No content-length cap on transcript uploads.** `TranscriptUploadRequest.content` has `min_length=1` but no `max_length`. A client can send an arbitrarily large body and it gets stored as-is in a `Text` column — a storage/memory abuse vector once this endpoint is reachable from outside localhost.

7. **No CI pipeline exists at all.** `docs/rules.md` R6.1 requires format/lint/test/security-scan to run on every PR. There is no `.github/workflows/` or equivalent — every check so far has been run manually, by me, in this session. Nothing stops a future change from silently breaking lint/tests/format if this session isn't the one making it.

## Medium — hygiene and supply chain

8. **ML model downloads aren't pinned.** `BAAI/bge-m3` (`ingestion/embeddings.py`) and the faster-whisper `"base"` model (`transcription/whisper_backend.py`) are pulled by name from Hugging Face Hub with no revision/commit hash pinned. A future run could silently fetch different weights than what was tested here.
9. **No CORS configuration yet.** Not wrong today (nothing calls the API cross-origin yet), but worth flagging now so it doesn't get added carelessly (e.g. `allow_origins=["*"]`) once the console (task 11) needs it.
10. **Interactive API docs exposed unconditionally.** FastAPI's default `/docs`, `/redoc`, `/openapi.json` are live with no gating. Fine for local dev; should be disabled or auth-gated before any non-local deployment.
11. **No rate limiting anywhere.**
12. **No structured logging** (rules.md R7.2) — also means no logs-based audit trail to fall back on given point 4 above.

## Low — worth knowing, not urgent

13. **No DB-level defense in depth for tenant isolation.** Every query correctly filters by `clinician_id` today (task 2's test proves it), but that's enforced entirely by application code remembering to do it every time. Postgres Row-Level Security policies would catch a future query that forgets the filter; nothing currently would.
14. **Guideline PDF provenance.** Already flagged in `docs/guideline_corpus/README.md`: the STG PDF comes from a third-party mirror, not an official government domain, and its edition is unverified. Not a code risk (it's just text fed through a parser), but worth remembering as a data-provenance gap, not just a security one.

## Non-security functional gaps, for completeness

- Full-corpus BGE-M3 embedding still hasn't been run (tracked in `docs/build_plan.md` task 3).
- Frontend has no API base URL configuration yet — not needed until task 11 actually calls the backend.
- `ingestion_queue` has no consumer yet (Layer 7.1 DDT agents, future work — already documented, not a surprise).

## Status

Items 1-4 fixed 2026-08-24 (see above). Items 5-7 are cheap, mechanical fixes (bind Postgres to localhost, add `max_length`, add a GitHub Actions workflow running what's currently run manually each task) — not done yet, deferred per user decision at the same time items 1-4 were fixed. Items 8-14 documented and deferred — they matter more as this gets closer to real deployment than they do for a single-clinician local pilot today. Revisit this whole file before any deployment beyond a local dev machine.
