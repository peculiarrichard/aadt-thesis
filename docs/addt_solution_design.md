# ADDT Project: Solution Design Document

Version 1.0
Status: For coding agent implementation
Owner: Peculiar Richard, M.Sc. Information Technology (AI), University of Lagos
Product name: not yet finalized, referred to below as "the system" or "the ADDT"

## 1. What this document is

This document tells a coding agent what to build. It is derived from an approved supervisor design document and from a supervisor-directed architecture (the Agentic Digital Twin Reference Architecture, referred to below as ADT-RA), and it reflects corrections the supervisor made to the original project direction. It is written to be implemented in phases, and several phases can start before the real clinician and real patient data are available. Section 11 marks exactly which parts those are.

Two academic artifacts sit behind this document and should not be contradicted by the code:

- A MIRG 2026 conference paper that presents ADT-RA and the AHDT/DDT case study.
- A UNILAG 2026 conference abstract that commits to a specific, bounded scope for the built system. The abstract says the system is built and evaluated in two modes with one consenting clinician, that consulting mode is evaluated only against retrospective, de-identified, already-dispositioned cases, and that live autonomous consultation on real patients is future work. The code must not go further than this without the design document being revised first.

## 2. Product in one paragraph

The system is a digital twin of one primary care doctor. It learns how that doctor thinks by watching real consultations and by structured question and answer sessions with the doctor. It represents the doctor as two separate twins joined by a connector: the Agentic Human Digital Twin (AHDT), which is the doctor as a person and the only part of the system that can act, and the Doctor Digital Twin (DDT), which is the doctor's medical knowledge and has no ability to act on its own. The system runs in two modes. In learning mode, active while the doctor is seeing real patients, it watches and updates the DDT. In consulting mode, it proposes a disposition for a patient case and asks the human doctor to approve, correct, or be escalated to whenever its confidence is low. The system is built for one doctor first, but every part of it is designed so that a second, third, and hundredth doctor can be added later without changing the architecture, only the data.

## 3. Core architectural decisions carried over from the supervisor's corrections

These points were specific corrections and additions from the supervisor and must be respected exactly as stated, since they are what changed the direction of the whole project.

1. The doctor is modeled as two twins, not one. The AHDT holds identity, credentials, and all agents, including the orchestrator. The DDT holds knowledge, case history, and reasoning models, and has no agentic layer of its own. They are joined by a Connector object.
2. The system has two operating modes, and both are part of the architecture, not an add-on. Learning mode is passive observation during real consultations. Consulting mode is active proposal generation when the doctor is unavailable, gated by a confidence threshold that triggers escalation to the human doctor.
3. The goal stated by the supervisor is that the twin should improve the doctor's practice and possibly match or exceed the doctor's skill over time. This is the design horizon. It is not a claim the pilot needs to prove. The pilot's job is to measure fidelity, not to prove superiority.
4. Training draws on every relevant learning method, not imitation alone: imitation learning from demonstrated decisions, supervised learning from written protocols and guidelines, reinforcement learning or direct preference optimization from the doctor's corrections, active learning to focus the doctor's limited time on the most uncertain cases, and case based reasoning to retrieve and adapt past precedent.
5. Explainability is a first class layer, not a feature bolted onto the model. Every agentic output must pass through an explanation step before it reaches a user.
6. A Connector is a reusable, typed, audited, policy governed class used to join any two twins. It is not a one off integration. The same Connector class joins the AHDT to the DDT, and later would join an AHDT to an organ twin or to another service.
7. The reference architecture has eight layers: physical, network and cloud, data ingestion, model, explainable AI, service, agentic, application. This is the layer numbering the code and file structure should mirror.
8. Multi tenancy is a day one schema decision, not a future migration. Every table and every service call carries a clinician identifier, even though the pilot populates it with exactly one clinician.

## 4. What the pilot actually builds, stated precisely

This section exists to stop scope drift. Read it before writing any code that touches autonomy or patient data.

Built and evaluated on the real doctor's real workflow: learning mode. The twin observes consultations and updates its models. Human review of every twin output before anything is used or shown to a patient.

Built and evaluated only in a synthetic and retrospective sandbox: consulting mode. The twin proposes a disposition for a held out, already decided, de-identified case, and its proposal is scored against what the doctor actually decided. No live patient ever receives a decision the twin generated without the doctor's review.

Never built in this phase: autonomous delivery of a clinical recommendation to a real patient without the doctor reviewing it first. Prescribing. Diagnostic confirmation. Multi clinician federation, meaning twins that learn from or influence each other. Any deployment beyond advisory.

If a request from anyone, including the product roadmap, asks the coding agent to connect consulting mode output directly to a real patient without a human review step in between, that request contradicts the approved design and the submitted abstract, and should be flagged rather than built.

## 5. System architecture

The system is organized into the eight ADT-RA layers. Each layer below states its purpose, what lives in it, and how it talks to the layers next to it.

### 5.1 Layer 1: Physical layer

The physical layer is the doctor and the patients as data sources, not code. It is represented in the system only through what Layer 2 captures from it: audio or text from consultations, structured protocol documents, and answers given during elicitation sessions. There is no physical layer code beyond the intake tooling described in Layer 2.

### 5.2 Layer 2: Network and cloud integration layer

Handles ingestion of consultation recordings or transcripts, protocol documents, and elicitation session transcripts into the system, and moves data between the intake tooling and the data layer. Must tolerate interrupted connections, since deployment targets include intermittent network settings. Implementation: a simple ingestion API with retry and local queuing before upload, so that a dropped connection during upload does not lose a consultation transcript.

### 5.3 Layer 3: Data ingestion layer

Two sublayers.

Sublayer 3.1, raw data: relational tables for the clinician profile, the consultation corpus, the protocol and guideline corpus, and the interaction log. See Section 7 for the schema.

Sublayer 3.2, structured knowledge: a vector store for embeddings of consultation cases and guideline passages, plus a knowledge graph or graph based retrieval index over the guideline corpus, so that guideline retrieval can follow relationships between conditions, symptoms, and recommended actions rather than pure similarity search alone.

### 5.4 Layer 4: Model layer

Holds three trained or configured components.

The persona policy: a parameter efficient fine tune (QLoRA) of an open weight base model, trained on the specific doctor's demonstrated decisions and elicitation transcripts. This is what encodes the doctor's individual style and thresholds.

The precedent memory: not a trained model, but the vector index of past cases from Layer 3.2, queried at inference time to retrieve the most similar precedent to a new case.

The guideline grounding component: a retrieval layer over the guideline corpus that supplies the formal, non negotiable standard of care. This component has veto power over the persona policy's output, described in Section 5.8 below.

### 5.5 Layer 5: Explainable AI layer

Holds one explanation method per model in Layer 4. For the persona policy and guideline grounding, this means the system must be able to state which retrieved cases or guideline passages informed a given output, not just produce the output. No output from Layer 7 reaches Layer 8 without an explanation object attached, generated here.

### 5.6 Layer 6: Service layer

Exposes every capability above as a callable, typed, tenant scoped service. Sublayers:

6.1 Connection services: the Connector class and its instances, including the AHDT to DDT Connector used in this pilot.

6.2 Data services: read and write access to Layer 3, scoped by clinician_id and by consent status.

6.3 AI, ML, and simulation services: model inference calls to Layer 4.

6.4 XAI services: explanation generation calls to Layer 5.

6.5 Cognitive services: higher level operations composed from the above, specifically perceive (structure an incoming case), reason (retrieve precedent and guideline, draft a disposition), and act (return the disposition with its explanation, or escalate).

Every service call in this layer takes a clinician_id parameter. This is the multi tenancy decision from Section 3, point 8, made concrete.

### 5.7 Layer 7: Agentic layer

Two sublayers, matching the AHDT and DDT split.

7.1 AI agents: DDT management agents, active in learning mode, which extract decisions and reasoning from a consultation transcript and route them to Layer 4 for training. DDT consultation agents, active in consulting mode, which query Layer 4 and Layer 6.5 to produce a disposition.

7.2 The orchestrator: the single decision point that determines which mode is active, whether an output's confidence clears the escalation threshold, and whether the constraint checker has passed a draft output before it is allowed to proceed to Layer 8. The orchestrator is also where the guideline veto rule executes: if the guideline grounding component's retrieved standard conflicts with the persona policy's draft, the guideline wins, and the conflict is logged and flagged to the doctor rather than silently resolved.

The reasoning loop is a minimal, explicit ReAct style loop: perceive the case, retrieve precedent and guideline, draft a disposition, run the constraint checker, attach an explanation, then either return the disposition (consulting mode, sandbox only, confidence above threshold) or escalate (confidence below threshold, or constraint checker failure, or guideline conflict). Implement this loop directly rather than through a heavyweight agent framework, so every step is inspectable and logged for the evaluation described in Section 10.

### 5.8 Layer 8: Application layer

The console, with two views.

Intake and case view: used to enter or select a case (real, during learning mode observation setup, or synthetic and retrospective, during consulting mode sandbox evaluation) and see the twin's structured summary and disposition with its explanation and confidence.

Clinician review queue and dashboard: where the doctor approves, corrects, or is shown escalated cases, and where the running concordance and calibration numbers described in Section 10 are visible.

## 6. Data capture and output delivery

This section states exactly how data gets into the system from the doctor and how the twin's output gets back to the doctor. Nothing here involves a wearable device. That decision is deliberate: an always-on device adds hardware cost and battery dependency the target deployment setting cannot assume, and it creates a second consent problem, since it can pick up a patient's voice without a clear moment where the patient agreed to that. Capture is explicit and doctor-controlled instead.

### 6.1 Input, real consultations, learning mode

The doctor starts and stops recording per patient, through a push-to-record control in the console, using the microphone on their own phone or laptop. There is no passive or continuous listening.

The audio is transcribed to text using a speech recognition model chosen for coverage of Nigerian languages and accents, not a generic English-only model, per the technology choices in Section 8 (Whisper and MMS are the two named candidates there).

The transcript is passed to the DDT management agents in Layer 7.1, which extract the case presentation, the doctor's decision, and the doctor's stated reasoning where available, and write this into the `consultations` table with `source_type = real_consultation`.

Recording a live consultation captures the patient's voice as well as the doctor's. This is a second consent requirement on top of the doctor's own consent, and it is the reason this input path is gated behind ethics clearance in Section 11, not available on day one.

### 6.2 Input, elicitation sessions and case review

The doctor works through synthetic or retrospective cases at a computer, on their own schedule, outside any live consultation. Input here is structured text, typed by the doctor or selected from structured fields (presenting complaint, history, examination findings, disposition, reasoning), not audio.

This is the primary input path for Phase 1, since it needs only the doctor's own consent and no patient is present. It produces `consultations` rows with `source_type = elicitation_session`.

The same structured interface is reused for the clinician review queue described in Section 6.3 above, where the doctor is reviewing a twin-generated draft rather than authoring a case from scratch.

### 6.3 Output, how the doctor receives what the twin produces

All output reaches the doctor through the console described in Layer 8. There is no delivery channel outside the console in this phase: no SMS, WhatsApp, or email push. Keeping every output inside one interface keeps the interaction log complete and auditable, which the evaluation in Section 10 depends on.

For a given case, the review queue screen shows: the structured case summary, the twin's proposed disposition, the confidence score behind it, the specific guideline passages and precedent cases the disposition drew on (the explanation object from Layer 5), and any guideline conflict flag raised by the orchestrator.

The doctor takes one of three actions on each item: approve, correct (edit the disposition and, where practical, note why), or handle directly (for cases the twin already escalated for low confidence, a guideline conflict, or a failed constraint check). Every action is written to `interaction_log.clinician_action`, and a correction never overwrites the twin's original draft, it is stored alongside it, so nothing is lost for later analysis.

### 6.4 Summary of the two input paths and the one output path

| | Path | When used | Consent needed | Available from |
|---|---|---|---|---|
| Input | Push-to-record audio, transcribed | Real consultations, learning mode | Doctor plus patient (per consultation) | After ethics clearance |
| Input | Structured typed form | Elicitation sessions, case review, retrospective cases | Doctor only | Day one |
| Output | Console review queue | Every twin-generated disposition, in every mode | N/A | Day one |

## 7. Data model

All tables include a `clinician_id` column even though the pilot populates it with one value.

```
clinicians
  clinician_id (pk)
  name
  specialty
  credentials
  standing_protocols_ref
  consent_status
  consent_date

consultations
  consultation_id (pk)
  clinician_id (fk)
  patient_ref (de-identified, not a real patient identifier)
  transcript_or_summary
  doctor_disposition
  doctor_reasoning_notes
  source_type (real_consultation | elicitation_session)
  ingested_at
  used_for_training (bool)
  used_for_holdout (bool)

guideline_documents
  document_id (pk)
  title
  edition
  source (e.g. Nigeria STG, WHO primary care)
  ingested_at

guideline_chunks
  chunk_id (pk)
  document_id (fk)
  content
  embedding

case_precedent_vectors
  vector_id (pk)
  clinician_id (fk)
  consultation_id (fk)
  embedding

interaction_log
  interaction_id (pk)
  clinician_id (fk)
  mode (learning | consulting_sandbox)
  input_case_ref
  draft_disposition
  final_disposition
  confidence_score
  guideline_conflict_flag (bool)
  escalated (bool)
  explanation_ref
  clinician_action (approved | corrected | escalated_review)
  clinician_correction_notes
  model_version
  created_at

consent_registry
  consent_id (pk)
  clinician_id (fk)
  subject_type (clinician | patient_data_batch)
  scope
  granted_at
  revoked_at

audit_log
  audit_id (pk)
  clinician_id (fk)
  actor (system | clinician | admin)
  action
  reference_table
  reference_id
  timestamp
```

The `interaction_log` table is the primary source for every evaluation metric in Section 10. Design it so nothing is overwritten; corrections create a new row rather than mutating the original.

## 8. Technology choices

| Component | Choice | Reason |
|---|---|---|
| Base model | Llama 3.1 8B Instruct, open weights | Fine tunes on a single 24 GB GPU, deployable on infrastructure inside Nigeria, keeps the twin inspectable |
| Fine tuning | QLoRA | Reproducible on a rented GPU within a thesis budget, adapters keep the base model swappable |
| Embeddings and vector store | BGE-M3 embeddings, pgvector on PostgreSQL | One database serves records, vectors, and logs, simple for a one person build |
| Knowledge graph / graph retrieval | Graph based RAG over the guideline corpus | Matches Layer 3.2 in the architecture, supports relational retrieval over conditions and recommendations |
| Backend | Python, FastAPI | Typed, testable, matches existing engineering background |
| Agent runtime | Custom minimal ReAct loop | Full transparency of every reasoning step, required for the evaluation and for the paper |
| Constraint checker | Deterministic rules compiled from the guideline corpus | Safety rules must be checkable, not probabilistic |
| Frontend | React | Standard, fast to build for both the intake and review interfaces |
| Inference serving | Quantized model (AWQ or GGUF) on modest hardware | Keeps cost near zero during development and the sandbox evaluation |

## 9. Safety mechanisms, required in every mode

Constraint checker: a deterministic rule set, compiled from the guideline corpus, that screens every draft disposition before it can proceed. A disposition that trips a red flag rule is converted into an escalation automatically, it is never shown as a normal output.

Abstention and escalation: the orchestrator computes a confidence score for every draft disposition. Below a configured threshold, the case is escalated to the doctor rather than answered. The threshold is a configuration value, not a hardcoded constant, since Section 10's evaluation will need to test it at different settings.

Guideline veto: described in 5.7. Any conflict between the persona policy's draft and the guideline grounding component's retrieved standard resolves in favor of the guideline, and the conflict is logged.

No silent autonomy increase: the mode (learning or consulting_sandbox) and the confidence threshold are both explicit configuration, changed only by deliberate action, never inferred or auto tuned by the system itself during this phase.

## 10. Evaluation design the system must support

The code must produce the data these metrics need, even though running the full evaluation depends on the real clinician's data.

Disposition concordance: top one agreement between the twin's disposition and the doctor's actual disposition on held out cases. Needs `interaction_log.final_disposition` compared against `consultations.doctor_disposition` for the same case.

Cohen's kappa: chance corrected agreement on the three disposition classes. Computed from the same comparison.

Severity weighted error matrix: errors classified by clinical consequence, with under triage weighted most heavily. Requires a severity label per disposition class pair, configured as a lookup table, not hardcoded in evaluation code.

Baseline comparison: the full twin (persona plus precedent plus guideline) against a guideline only agent with no persona fine tune and no precedent memory, run over the same held out case set. This requires the guideline only agent to be a real, separately invocable configuration of Layer 7, not a theoretical comparison.

Ablations: guideline only, guideline plus precedent, guideline plus persona, full system. Same requirement as above, each must be a runnable configuration.

Review queue behavior: acceptance rate, correction rate, and escalation rate, computed from `interaction_log.clinician_action` over time.

## 11. Build sequence and what can start now

This sequence follows the Data Twin, Model Twin, Agent Twin progression. Items marked CAN START NOW need no real clinician data. Items marked NEEDS CLINICIAN need the confirmed doctor, consent, or ethics clearance as stated.

### Phase 1: Data Twin

- CAN START NOW: repository scaffold, environment setup, GPU access provisioned.
- CAN START NOW: database schema from Section 7, built and tested with synthetic dummy rows.
- CAN START NOW: guideline corpus ingestion pipeline, Layer 3.1 and 3.2, run against the real Nigerian STG and WHO primary care documents, which are public.
- CAN START NOW: de-identification pipeline, built and tested against synthetic fake patient records the developer writes.
- CAN START NOW: a synthetic case set of ten to twenty primary care cases across the three disposition classes, for later use in elicitation sessions and as an early test set for the baseline agent.
- NEEDS CLINICIAN: ingestion of the real doctor's standing protocols, once the doctor is confirmed and has given consent.
- NEEDS CLINICIAN: elicitation session transcripts.
- NEEDS CLINICIAN AND ETHICS CLEARANCE: retrospective real consultation records.

### Phase 2: Model Twin

- CAN START NOW: the guideline only baseline agent, Layer 4 guideline grounding plus Layer 7 orchestrator with no persona policy, tested against the synthetic case set.
- CAN START NOW: the constraint checker, compiled from the public guideline corpus.
- NEEDS CLINICIAN DATA: the persona policy fine tune, which requires real or elicited decisions from the doctor.
- NEEDS CLINICIAN DATA: precedent memory populated with real cases.
- Deliverable once clinician data exists: offline evaluation comparing the full twin against the guideline only baseline, per Section 10.

### Phase 3: Agent Twin

- CAN START NOW: the console shell for both views in Layer 8, built against mock data.
- CAN START NOW: the full service layer (6.1 through 6.5) with clinician_id scoping, tested against dummy tenants.
- NEEDS CLINICIAN DATA: connecting the console and service layer to the real persona policy and precedent memory once Phase 2 completes.
- NEEDS CLINICIAN, LEARNING MODE: shadow deployment where the twin observes real consultations.
- NEEDS RETROSPECTIVE DATA: consulting mode sandbox evaluation against held out, already dispositioned cases.

## 12. Explicit non-goals for this build

Do not build patient facing delivery of a twin generated disposition without a clinician review step in between.

Do not build cross clinician federation, meaning any mechanism by which one doctor's twin trains on or influences another doctor's twin. The schema supports multiple tenants existing side by side; it must not let them interact.

Do not build automatic mode switching from learning to consulting based on the system's own judgment of readiness. Mode is set by explicit configuration during this phase.

Do not skip the constraint checker or the explanation step for any output, including outputs generated during development or testing, since the habit of bypassing safety steps in a dev environment tends to leak into what ships.

## 13. Definition of done for this phase

The build for this thesis and paper cycle is complete when the following all hold: the guideline only baseline runs end to end against the synthetic case set, the persona policy has been fine tuned on real clinician data and evaluated for concordance and kappa against a held out split, the ablation set from Section 10 is runnable and produces comparable results, the console supports the full review queue workflow, and the interaction log contains enough structured data to write the results section of the paper without manual reconstruction.
