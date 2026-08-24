# Build Log

A narrative record of how Phase 1 was actually built: decisions made, gaps found in the design doc and how they were resolved, bugs hit and fixed, and things deliberately deferred. `docs/build_plan.md` is the checklist (what's done); `docs/security_review.md` is the security audit; this is the "why" and "what happened" behind both. Written retrospectively after Phase 1 completed, not word-for-word — captures the important details and reasoning, not the full transcript.

## Planning, before any code

Started by reading `docs/addt_solution_design.md` in full, then brainstorming the technical shape before writing anything, per instruction. Key decisions locked in during that discussion:

- **Monorepo**: `/backend` (FastAPI), `/frontend` (React/Vite/TS), `/docs`, single `docker-compose.yml`.
- **DB**: local Postgres + pgvector via Docker Compose, not a hosted service.
- **Tooling**: `uv` for Python, Vite + TypeScript for the frontend.
- **Synthetic data authorship**: Claude drafts, user reviews before anything downstream treats it as final — applied later to the synthetic case set (task 5).
- **GPU/fine-tuning**: deferred entirely — the persona policy fine-tune needs real clinician data that doesn't exist yet, so no point provisioning compute for it now.
- **Constraint checker and knowledge graph**: proposed as plain declarative rules (YAML) and Postgres edge tables respectively, rather than a rules-engine library or a separate graph database — matches the design doc's own "simple, one database, inspectable" ethos from Section 8.

Then found `docs/rules.md` (a generic engineering-rules file) and hit two real conflicts with what had just been agreed:

- **R11.3 says `docs/` should be git-ignored**, but the design doc and build plan explicitly live there and need to be tracked. Resolved: track `docs/` anyway for this project, deviating from R11.3 — these are thesis artifacts, not agent scratch notes.
- **R3-R4 assume a PR/reviewer workflow**, but this is a solo repo with no remote yet. Resolved: commit directly to main for now (though as it turned out, no commits were made at all during this session — every task was implemented and verified, with commits explicitly left for the user to do themselves).

Wrote `docs/build_plan.md`: the Section 11 task list, split into "CAN START NOW" (Phase 1-3 items buildable without the real clinician) and "NEEDS CLINICIAN" (blocked). One more scope call made at this stage: the push-to-record UI/STT pipeline (Section 6.1) isn't explicitly marked CAN-START-NOW in the design doc, but the code path itself doesn't need real patient audio — folded it into Phase 1 as task 7, testable against non-patient sample audio.

## Task 1 — Repo scaffold

Straightforward: `uv init` for the backend (FastAPI, ruff, pytest), Vite+TS for the frontend (oxlint, Prettier, Vitest — stripped the default Vite/React marketing boilerplate down to a minimal placeholder since the real console is task 11's job), `docker-compose.yml` for Postgres+pgvector, root `.gitignore`/`CONTRIBUTING.md`/`README.md`, `docs/setup.md` as the running "how to run this" reference. Verified pgvector's `CREATE EXTENSION` actually works before moving on.

## Task 2 — DB schema

Implemented Section 7's schema as SQLAlchemy models + Alembic migrations. One real ambiguity surfaced here: Section 3.8 says *every* table carries `clinician_id`, but Section 7's printed schema for `guideline_documents`/`guideline_chunks` omits it. Asked the user rather than guessing — confirmed: omit it, since guideline corpus (Nigeria STG, WHO docs) is shared public knowledge, not tenant-owned data. Section 7 read literally, Section 3.8 treated as the general principle it's an exception to.

Two real bugs found and fixed while building this:

1. **Alembic autogenerates `CREATE TABLE` with enum columns, but `op.drop_table()` on downgrade doesn't drop the Postgres ENUM type it implicitly created.** Running upgrade → downgrade → upgrade failed with "type already exists" on the second upgrade. Fixed by adding explicit `postgresql.ENUM(name=...).drop(bind, checkfirst=True)` calls at the end of every migration's `downgrade()` — a pattern repeated in every migration since.
2. **Windows' default TCP connect timeout is ~130 seconds.** The tenant-isolation test's "skip if DB unreachable" fixture took over 2 minutes to notice the DB was down before skipping — bad enough that anyone running `pytest` without Docker running would think the suite had hung. Fixed with an explicit 3-second `connect_timeout` on the SQLAlchemy engine; skip now takes ~14 seconds.

Seed script (`db/seed.py`) written to prove tenant isolation with 2 synthetic clinicians — this became load-bearing later (see task 6's bug below).

## Task 3 — Guideline corpus ingestion

Sourced two real public documents rather than fabricating test data: the Nigeria Standard Treatment Guidelines and the WHO PEN (Package of Essential Noncommunicable Disease Interventions). Real friction here:

- The first Nigeria STG PDF found (WHO's own 2016 2nd-edition mirror) turned out to be a 1089-page **scanned image with zero extractable text** — rejected as unusable without OCR, which was out of scope. A second source (a third-party policy mirror, policyvault.africa) had real extractable text, but its claimed "2022 3rd edition" label doesn't match the PDF's own metadata (dated ~2008-2015) or its acknowledgements page ("the first edition..."). Used it anyway with the edition honestly recorded as unverified, per the user's explicit instruction, with the gap tracked in `docs/guideline_corpus/README.md` pending a better source.
- Built the pipeline (PDF extract → chunk → embed → graph-extract) as a real, working thing, not a mock. Checked with the user before committing to two costly steps: running real BGE-M3 embeddings (a ~2.5GB download) and how to extract the condition/symptom/recommendation graph the design doc calls for but never gives a schema for. Landed on: run BGE-M3 for real via a smoke test (proves the integration works) but defer the full ~1,000-chunk corpus embedding run to later, documented as an open gap rather than silently skipped; use deterministic heading/keyword extraction for the graph (matches the project's "rules, not black boxes" philosophy already used for the constraint checker) rather than an LLM call.
- Designed `guideline_graph_nodes`/`guideline_graph_edges` from scratch (not in Section 7, same situation as before) and validated the graph extraction honestly: it works and produces real relationships, but is genuinely noisy on the STG's two-column PDF layout (labels and their content sometimes separate during linear text extraction) — verified this by running it against all 652 real chunks and inspecting actual output, not just unit tests on clean synthetic text. Documented the limitation rather than overclaiming precision.
- Two more bugs found: `seed.py` would have destroyed real ingested guideline data on re-run (it deleted `guideline_chunks`/`guideline_documents` indiscriminately) — fixed by scoping the seed script to tenant-only tables, since guideline data isn't tenant-scoped and doesn't belong to it. And importing the embeddings module at test-collection time (even in a test that's skipped) added 100+ seconds to *every* future `pytest` run — fixed by deferring the heavy import into the test function body, a pattern then reused for the transcription smoke test in task 7.

## Task 4 — De-identification pipeline

Deterministic regex-based redaction (name via title+capitalized-word heuristic, phone, email, national ID, date, address) — chosen over an NER/ML approach for the same "inspectable, not probabilistic" reason as the graph extraction. Documented its real limitation up front rather than overselling it: title-less names aren't caught. Validated against the full real 652-chunk STG corpus as a false-positive check — zero spurious redactions on clinical content; the only hits were the document's own front matter (real credited contributors, the ministry's address), which is structurally correct behavior. Also built `generate_patient_ref()`, deliberately never reading the transcript at all, since even a perfectly-scrubbed transcript still shouldn't be the source of a patient identifier.

## Task 5 — Synthetic case set

Before drafting content, surfaced a real gap: Section 10 requires evaluating "the three disposition classes" but the design doc never names them — and a placeholder ("treat"/"refer"/"observe") had already been improvised in `seed.py` without that being a real decision. Flagged it and got the user's sign-off on `manage_at_primary_care` / `refer_routine` / `refer_urgent_emergency`, severity-ordered for Section 10's severity-weighted error matrix, defined in a new `disposition.py` module and retrofitted into `seed.py`.

Drafted 15 cases (5 per class), each grounded in a condition label already extracted into `guideline_graph_nodes` from the real STG corpus — verified all 15 match exactly, so later retrieval testing has a real match to find rather than a fabricated one. Marked prominently in both `build_plan.md` and `setup.md` as Claude-drafted, not yet clinician-reviewed.

## Task 6 — Layer 2 ingestion API

Scoped deliberately before building: Section 5.2 asks for "retry and local queuing," but true client-side local queuing needs a console (Layer 8) that doesn't exist yet. Built the server-side half honestly — an idempotent upload endpoint backed by a new `ingestion_queue` table (again not in Section 7, same situation as the graph tables) — and documented the scope boundary explicitly rather than silently under-delivering against the checklist wording.

One more real bug: reusing the existing `source_type` Postgres enum type across two tables (`consultations` and the new `ingestion_queue`) should have been simple via SQLAlchemy's `create_type=False`, but that flag silently doesn't propagate through the generic `sa.Enum` → Postgres-dialect adaptation in the SQLAlchemy version in use — the migration kept trying to `CREATE TYPE source_type` a second time and failing. Fixed by using `postgresql.ENUM` directly instead of the generic wrapper, in both the model and the migration.

This endpoint later turned out to be where the security review (below) found its most important findings.

## Task 7 — Push-to-record + transcription scaffold

Real environment constraint hit immediately: no system `ffmpeg`, which the standard `openai-whisper` package requires unconditionally. Switched to `faster-whisper`, which decodes audio via PyAV (bundles its own FFmpeg libraries in the wheel) — avoided a system dependency the target deployment environment might not reliably have either.

Needed non-patient sample audio to test against without a microphone in this environment. Generated it offline via Windows' built-in SAPI text-to-speech (`pyttsx3`, used once to create the fixture file then removed — not a permanent dependency), producing an unambiguous synthetic test phrase rather than sourcing or fabricating anything that could be mistaken for real audio. Real smoke test (downloads the actual model) passed — transcribed the synthetic audio correctly.

Frontend push-to-record component built and tested standalone (mocking `MediaRecorder`/`getUserMedia`), deliberately not wired into a console page since that composition belongs to task 11. Explicit start/stop only, matching Section 6.1's "no passive or continuous listening" requirement directly in the component's behavior.

This closed out Phase 1 (all 7 tasks) with no commits made at any point — every change was left staged for the user to review and commit.

## Post-Phase-1 security and gap review

Asked to review everything built so far for gaps and security. Re-read the actual code rather than relying on memory of what was built, and found a pattern: **two modules built specifically to protect patient-adjacent data (de-identification, task 4; the tenant-scoped schema, task 2) were never actually wired into the one API that touches that data (the ingestion API, task 6).** Concretely:

1. No authentication at all — any caller could supply any `clinician_id`.
2. `deidentify_text()` was never called — raw content stored verbatim.
3. `clinicians.consent_status` was never checked, despite Section 5.6.2 explicitly requiring data services to be "scoped by clinician_id and by consent status."
4. `audit_log` existed in the schema but nothing outside the seed script ever wrote to it.

Also found and documented, but left deferred per the user's explicit scope choice: Postgres bound to all network interfaces with a well-known dev password, no content-length cap on uploads, no CI pipeline despite `rules.md` requiring one, unpinned ML model downloads, no CORS config, API docs exposed unconditionally, no rate limiting, no structured logging, no DB-level row-security as defense-in-depth.

Fixed items 1-4 the same session, after checking with the user on the one real architectural choice involved (auth approach): a single shared service API key (not per-clinician — there's no login system yet to authenticate a specific clinician against), required via an `X-Service-Api-Key` header. De-identification now runs before any storage or comparison; only a category-count `redaction_summary` (never the redacted values) is persisted or returned. Uploads are rejected with 403 unless consent is `"granted"`. Every accepted upload, including idempotent replays, now writes an audit log row. Verified with 5 new integration tests against the real database, on top of the 6 already there.

`docs/security_review.md` is the living reference for what's fixed and what's still deferred — read it before this goes anywhere beyond a local, single-clinician dev machine.

## Where things stand

Phase 1 (Data Twin) is fully checked off in `docs/build_plan.md`. Phase 2 (Model Twin) starts with the constraint checker (task 8). Real gaps still open and tracked, not hidden: the Nigeria STG PDF's edition is unverified, full-corpus BGE-M3 embedding hasn't been run, and everything in `docs/security_review.md`'s deferred list is still deferred.
