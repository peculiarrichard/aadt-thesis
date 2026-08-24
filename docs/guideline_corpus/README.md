# Guideline Corpus Sources

Raw source documents for the guideline ingestion pipeline (Phase 1, `docs/build_plan.md` task 3). Both are public documents; downloaded 2026-08-24.

## `nigeria_stg.pdf` — Nigeria Standard Treatment Guidelines

- Downloaded from: `https://www.policyvault.africa/wp-content/uploads/policy/NGA103.pdf`
- Publisher per document content: Federal Ministry of Health, Nigeria, with WHO.
- **Edition caveat, unresolved:** policyvault.africa labels this "January 2022," but the PDF's own metadata (`CreationDate`) is 2009 and the acknowledgements page reads "the first edition of the Nigerian Standard Treatment Guidelines," with production described as starting in 2005. This is most likely the 1st or 2nd edition content, not the 3rd edition (2022) the Federal Ministry of Health officially launched in November 2022 — that edition does not appear to have an official, freely downloadable PDF as of this writing (only paywalled/unofficial copies on sites like Scribd were found). **Treat the edition label as unverified.** The 2016 2nd edition PDF hosted at `extranet.who.int` was also checked and rejected: it's a 1089-page scanned image with no extractable text layer, unusable without OCR.
- Action needed: replace with a verified official edition once available (see `docs/build_plan.md`, Phase 1, "NEEDS CLINICIAN" is not the blocker here — this is just a sourcing gap, revisit independent of clinician availability).
- 116 pages, real text layer, structured by body-system chapters with per-condition fields (Introduction, Clinical features, Differential diagnoses, Complications, Investigations, Treatment objectives, Non-drug treatment, Drug treatment, Caution).

## `who_pen.pdf` — WHO Package of Essential Noncommunicable Disease Interventions (PEN) for Primary Health Care

- Downloaded from: `https://www.afro.who.int/sites/default/files/2017-06/9789241506557_eng.pdf` (WHO's own regional office domain).
- 210 pages, real text layer, protocol/algorithm-style structure (e.g. ASK/ADVISE/ASSESS/ASSIST/ARRANGE steps) rather than the STG's per-condition fields — the ingestion pipeline's deterministic graph extraction is tuned to the STG's structure and will likely produce few or no graph nodes/edges from this document. Still usable for guideline_chunks/retrieval; the graph gap is a known limitation, not a bug.

## Ingesting these documents

See `backend/src/backend/ingestion/` and `docs/setup.md` for how to run the pipeline against these files.
