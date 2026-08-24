# ADDT — Agentic Digital Twin

A digital twin of one primary care doctor, built as part of an M.Sc. thesis (University of Lagos). The system watches real consultations to learn how the doctor thinks (learning mode) and proposes dispositions for review on retrospective cases (consulting mode), with a human doctor approving, correcting, or escalating every output.

## Where to start

- [`docs/addt_solution_design.md`](docs/addt_solution_design.md) — the solution design document. Read this first; nothing in this repo should contradict it.
- [`docs/build_plan.md`](docs/build_plan.md) — the implementation task checklist, tracking what's done and what's blocked on the clinician.
- [`docs/setup.md`](docs/setup.md) — how to run the database, backend, and frontend locally.
- [`docs/rules.md`](docs/rules.md) / [`CONTRIBUTING.md`](CONTRIBUTING.md) — engineering rules this repo follows.

## Layout

```
backend/    FastAPI service (Python, uv)
frontend/   React console (TypeScript, Vite)
docs/       Design docs, build plan, and setup instructions (tracked in git)
```
