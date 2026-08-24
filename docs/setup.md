# Local Development Setup

Covers the repo scaffold: the Postgres+pgvector database, the FastAPI backend, and the React frontend.

## Prerequisites

- Docker Desktop (for the database)
- [`uv`](https://docs.astral.sh/uv/) (Python env/dependency manager)
- Node.js 22+ and npm

## 1. Database

```
cp .env.example .env   # first time only; edit if you want non-default credentials
docker compose up -d
```

This starts a single `db` service (`pgvector/pgvector:pg16`) on `localhost:5432`, with credentials from `.env` (defaults: user `addt`, db `addt`, password `addt_dev_password` — dev-only, not meant to be secure). Data persists in the `addt_pg_data` Docker volume across restarts.

Check it's healthy:

```
docker compose ps
```

Stop it with `docker compose down` (add `-v` to also wipe the data volume).

### Schema migrations

The `vector` extension and every table from the solution design's Section 7 are created by Alembic migrations, not by `docker-compose.yml` itself:

```
cd backend
uv run alembic upgrade head    # apply all migrations
uv run alembic downgrade base  # drop everything (dev only)
```

`backend/src/backend/db/models.py` holds the SQLAlchemy models; `backend/alembic/versions/` holds the migration history. When you change a model, generate a new migration with `uv run alembic revision --autogenerate -m "description"`, then read the generated file before applying it — Alembic does not reliably autogenerate Postgres ENUM type drops on downgrade, so check any new enum columns get an explicit `postgresql.ENUM(name=...).drop(...)` in `downgrade()` (see the initial migration for the pattern).

### Seed data

```
cd backend
uv run python -m backend.db.seed
```

Clears and re-inserts synthetic dummy rows (2 fake clinicians, consultations, interaction log entries, precedent vectors) — safe to re-run. This is not real clinician or patient data; see `docs/build_plan.md` for what's still blocked on the real clinician. It deliberately does not touch `guideline_documents`/`guideline_chunks`/`guideline_graph_*` — those are shared, not tenant-scoped, and owned by the ingestion pipeline below, not by this seed script.

### Disposition classes

The solution design requires evaluating "the three disposition classes" (Section 10) but never names them. `backend/src/backend/disposition.py` defines them: `manage_at_primary_care`, `refer_routine`, `refer_urgent_emergency`, severity-ordered so an under-triage error (predicting a lower index than the true one) is easy to detect. `consultations.doctor_disposition` and `interaction_log.draft_disposition`/`final_disposition` are free-text columns (Section 7), but their value is expected to be one of these three strings — this is a project decision, not something Section 7 states explicitly, so revisit it if the supervisor's terminology differs.

### Synthetic case set

`backend/src/backend/fixtures/synthetic_cases.yaml` — 15 cases (5 per disposition class), loaded and schema-validated by `backend/src/backend/fixtures/loader.py` (`load_synthetic_cases()`). **Claude-drafted clinical content, not yet clinician-reviewed** — do not treat it as real evaluation ground truth until reviewed. Each case is grounded in a condition label already extracted into `guideline_graph_nodes` from the real STG corpus, so retrieval against the guideline corpus has a real match to find.

### Guideline corpus ingestion

Source PDFs live in `docs/guideline_corpus/` (see that folder's `README.md` for provenance and a known caveat about the Nigeria STG edition). Ingest one with:

```
cd backend
uv run python -m backend.ingestion.pipeline --file "../docs/guideline_corpus/nigeria_stg.pdf" --title "Nigeria Standard Treatment Guidelines" --source "Federal Ministry of Health Nigeria / WHO" --edition "unverified (see docs/guideline_corpus/README.md)"
uv run python -m backend.ingestion.pipeline --file "../docs/guideline_corpus/who_pen.pdf" --title "WHO Package of Essential Noncommunicable Disease Interventions (PEN)" --source "WHO"
```

This parses the PDF (`backend/src/backend/ingestion/pdf_extract.py`), chunks it (`chunking.py`), embeds every chunk with BGE-M3 (`embeddings.py`, Section 8), and runs deterministic heading/keyword graph extraction (`graph_extraction.py`, Section 5.3) — all written via `pipeline.py` to `guideline_documents`, `guideline_chunks`, `guideline_graph_nodes`, and `guideline_graph_edges`. Add `--no-embed` to skip the BGE-M3 step (chunks get `embedding = NULL`) — useful for quickly re-verifying the parse/chunk/graph steps without paying the model cost again.

**Embedding cost:** the first run downloads the BGE-M3 model (~2.5GB, one-time) and then embeds every chunk on CPU. Budget low tens of minutes for the full two-document corpus (~1,000 chunks). This has not been run for the full corpus yet as of writing — see `docs/build_plan.md` task 3 for status. The integration itself is verified for real via the smoke test below; only the full-corpus run is pending.

Each invocation always creates a new `guideline_documents` row — it does not update or deduplicate an existing one. Re-ingesting the same file twice produces two documents' worth of chunks/nodes/edges; if you need to redo an ingestion, delete the old document's rows first (cascade is not configured, so delete `guideline_graph_edges` → `guideline_graph_nodes` → `guideline_chunks` → `guideline_documents`, scoped to that `document_id`).

**Known limitation:** graph extraction assumes a subheading label ("Clinical features", "Treatment objectives", ...) is immediately followed by its content in reading order. The Nigeria STG PDF uses a layout that `pypdf` extracts in a way that sometimes separates a label from its own content — extraction is real but noisy for that document (e.g. some "symptom" or "recommendation" nodes are actually prevention/causes text). The WHO PEN document uses a different, protocol-style structure and yields few or no graph nodes at all. See `backend/src/backend/ingestion/graph_extraction.py`'s module docstring and `docs/guideline_corpus/README.md`.

## 2. Backend (FastAPI)

```
cd backend
uv run uvicorn backend.main:app --reload
```

Serves on `http://127.0.0.1:8000`. Health check: `GET /health` → `{"status": "ok"}`. Interactive API docs: `http://127.0.0.1:8000/docs`.

### Ingestion API (Layer 2, Section 5.2)

Every request needs the shared service API key in a header: `X-Service-Api-Key: <INGESTION_API_KEY from .env>`. Missing or wrong key returns `401`. See `docs/security_review.md` item 1 for why this exists and its limits (it authenticates "trusted intake tooling," not a specific clinician — there's no per-clinician login yet).

`POST /ingestion/transcripts` — upload a raw transcript, idempotent per `(clinician_id, idempotency_key)`:

```json
{
  "clinician_id": "<uuid of an existing, consented clinician>",
  "idempotency_key": "<client-generated unique string>",
  "source_type": "real_consultation" | "elicitation_session",
  "content": "<transcript text, max 200,000 chars>"
}
```

Before storage, `content` is run through `backend.deidentify.deidentify_text()` (task 4) — only the de-identified text is ever persisted. The response includes `redaction_summary` (e.g. `{"PHONE": 1}`), a count per category of what was redacted, never the redacted values themselves. `clinicians.consent_status` must be `"granted"` or the request is rejected with `403` before anything is stored. Every accepted upload (including idempotent replays) writes an `audit_log` row (`action = "ingestion_upload"` or `"ingestion_upload_replay"`).

Retrying with the same `idempotency_key` and identical body returns the original result (`200`, `idempotent_replay: true`) instead of creating a duplicate — this is what makes the endpoint safe for a client to call again after a dropped connection. The same key with *different* (de-identified) content returns `409` (a real client bug, not a legitimate retry). An unknown `clinician_id` returns `404`.

`GET /ingestion/transcripts?clinician_id=<uuid>` lists that clinician's queued items (tenant-scoped, per Section 6.2).

**Scope boundary:** this is the server-side half only. "Local queuing" — the intake tooling buffering a transcript on the doctor's device until it gets a confirmed success response — is a Layer 8 (console) responsibility, not yet built (`docs/build_plan.md` task 11). Uploaded items land in `ingestion_queue`, not `consultations` — per Section 6.1, the DDT management agents (Layer 7.1, not yet built) are what read from the queue and write structured fields into `consultations`.

### Transcription backend (Section 6.1/Section 8)

`backend/src/backend/transcription/whisper_backend.py` — `transcribe_audio(path)` using `faster-whisper` (not the original `openai-whisper` package: this dev environment has no system `ffmpeg`, which `openai-whisper` requires; `faster-whisper` decodes via PyAV, which bundles its own FFmpeg libraries in the wheel). `MODEL_SIZE = "base"` is a scaffold choice for fast local testing, not a final Nigerian-language accuracy decision — Section 8 names both Whisper and MMS as candidates; that choice, and model size, should be revisited once real consultation audio exists to evaluate against (gated behind ethics clearance).

Smoke test (real, downloads the model — skipped by default like the embedding smoke test):

```
RUN_TRANSCRIPTION_SMOKE_TEST=1 uv run pytest tests/test_transcription_smoke.py
```

Transcribes `tests/fixtures/sample_audio.wav` — synthetic, non-patient audio generated offline via Windows SAPI text-to-speech (provenance and regeneration steps in that folder's `README.md`) — and checks the output contains recognizable words. As with the embeddings smoke test, do not import `backend.transcription.whisper_backend` at module level in any file pytest collects automatically; keep the import inside the test body.

**Not switched on for real consultations.** This is a code-path scaffold only — the push-to-record UI component (`frontend/src/components/PushToRecordButton.tsx`) is not wired into any console page, and this backend isn't called from the ingestion API. Both need patient consent and ethics clearance (Section 6.1, `docs/build_plan.md` Phase 1) before they're connected to real consultations.

Commands:

```
uv run pytest              # run tests
uv run ruff check .        # lint
uv run ruff format .       # format
```

## 3. Frontend (React console)

```
cd frontend
npm install   # first time only
npm run dev
```

Serves on `http://localhost:5173` by default.

Commands:

```
npm run test           # run tests (Vitest)
npm run lint            # lint (oxlint)
npm run format          # format (Prettier, writes)
npm run format:check    # format (Prettier, check only)
npm run build            # type-check + production build
```

## Configuration

Environment variables live in `.env` at the repo root (gitignored; see `.env.example` for the required keys). Never commit real credentials — this scaffold's defaults are for local dev only and are not used anywhere else.

## Testing instructions

- Backend: `cd backend && uv run pytest`.
  - `tests/test_health.py`, `tests/test_chunking.py`, `tests/test_graph_extraction.py`, `tests/test_deidentify.py`, `tests/test_synthetic_cases.py` need no database and no heavy dependencies.
  - `tests/test_db_tenant_isolation.py` needs the database running (`docker compose up -d` first) — it seeds synthetic data for 2 fake clinicians and asserts clinician-scoped queries never return another clinician's rows. It's automatically skipped (not failed) if the database is unreachable.
  - `tests/test_ingestion_api.py` also needs the database running (same skip-if-unreachable behavior) — covers retry-idempotency, the 409/404 error cases, and tenant scoping for the ingestion API above.
  - `tests/test_embeddings_smoke.py` and `tests/test_transcription_smoke.py` are skipped by default (download the real BGE-M3 / faster-whisper models). Run explicitly with `RUN_EMBEDDING_SMOKE_TEST=1 uv run pytest tests/test_embeddings_smoke.py` or `RUN_TRANSCRIPTION_SMOKE_TEST=1 uv run pytest tests/test_transcription_smoke.py`. **Do not import `backend.ingestion.embeddings` or `backend.transcription.whisper_backend` at module level in any file pytest collects automatically** — those imports cost 10s-100s of seconds even when the test that uses them is skipped, and that cost is paid by every `pytest` invocation, not just that file. Keep such imports inside the test function body (see either file for the pattern).
- Frontend: `cd frontend && npm run test` — the `App` smoke test plus 4 `PushToRecordButton` tests (mocked `MediaRecorder`/`getUserMedia`, no real microphone needed).
- Database only: `docker compose up -d`, then `docker compose exec db psql -U addt -d addt -c "SELECT extname FROM pg_extension WHERE extname='vector';"` should return one row after running migrations.

## What's not here yet

The constraint checker, the agent layer, and the real console views are separate tasks — see `docs/build_plan.md` for the full checklist and current status. The guideline corpus is ingested but full-corpus BGE-M3 embedding has not been run (see the ingestion section above).
