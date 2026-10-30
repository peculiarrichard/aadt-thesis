"""Real-time patient-chat intake (Phase W, simulated patients only): the twin
asks history-taking questions turn by turn over a WebSocket, grounded in the
doctor's own precedent cases, then hands off to the existing run_twin_agent
once enough has been gathered. Session auth reuses the same signed cookie as
every other route -- Starlette's SessionMiddleware (main.py) populates
scope["session"] for the websocket scope exactly as it does for http, so no
new auth mechanism is needed.

Blocking calls (the LLM turn, the embedding call, running the twin) are
pushed to a thread via run_in_threadpool so one patient's chat can't stall
the single-worker server for everyone else (the doctor's console included).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.agents.patient_intake_agent import IntakeParseError, next_intake_turn
from backend.agents.precedent_retrieval import retrieve_precedent_cases
from backend.agents.report_builder import ClericalDetails
from backend.api.deps import PatientIdDep, SessionDep
from backend.config import get_settings
from backend.db.enums import ChatRole, PatientChatStatus
from backend.db.models import Patient
from backend.db.session import get_session
from backend.services import patient_chat_service

router = APIRouter(prefix="/patient/chat", tags=["patient-chat"])


class CreateSessionRequest(BaseModel):
    clinician_id: str
    presenting_complaint: str
    patient_age: str | None = None
    patient_sex: str | None = None
    temperature: str | None = None
    blood_pressure: str | None = None
    pulse_rate: str | None = None
    respiratory_rate: str | None = None
    oxygen_saturation: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str


@router.post("/sessions", response_model=CreateSessionResponse)
def create_chat_session(
    body: CreateSessionRequest, patient_id: PatientIdDep, session: SessionDep
) -> CreateSessionResponse:
    chat = patient_chat_service.create_session(
        session,
        patient_id,
        uuid.UUID(body.clinician_id),
        body.presenting_complaint,
        ClericalDetails(
            age=body.patient_age,
            sex=body.patient_sex,
            temperature=body.temperature,
            blood_pressure=body.blood_pressure,
            pulse_rate=body.pulse_rate,
            respiratory_rate=body.respiratory_rate,
            oxygen_saturation=body.oxygen_saturation,
        ),
    )
    return CreateSessionResponse(session_id=str(chat.session_id))


class ChatSessionOut(BaseModel):
    session_id: str
    status: str
    pending: bool
    report: dict | None


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_chat_session(
    session_id: uuid.UUID, patient_id: PatientIdDep, session: SessionDep
) -> ChatSessionOut:
    chat = patient_chat_service.get_session_for_patient(session, patient_id, session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    pending = chat.status != PatientChatStatus.RESOLVED
    report = chat.draft_report if pending else chat.final_report
    return ChatSessionOut(
        session_id=str(chat.session_id), status=chat.status.value, pending=pending, report=report
    )


@router.websocket("/ws/{session_id}")
async def chat_ws(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_session)],
) -> None:
    patient_id_raw = websocket.session.get("patient_id")
    if not patient_id_raw:
        await websocket.close(code=4401)
        return
    patient_id = uuid.UUID(patient_id_raw)

    chat = patient_chat_service.get_session_for_patient(db, patient_id, session_id)
    if chat is None:
        await websocket.close(code=4404)
        return
    if chat.status != PatientChatStatus.IN_PROGRESS:
        await websocket.close(code=4409)
        return

    await websocket.accept()

    def _load_precedent() -> list:
        from backend.ingestion.embeddings import embed_texts  # deferred: heavy (BGE-M3/torch)

        query_embedding = embed_texts([chat.case_text or ""])[0]
        return retrieve_precedent_cases(db, chat.clinician_id, query_embedding)

    precedent_cases = await run_in_threadpool(_load_precedent)
    existing_messages = patient_chat_service.list_messages(db, session_id)
    history = [{"role": m.role.value, "content": m.content} for m in existing_messages]

    try:
        if len(existing_messages) <= 1:
            # Fresh session -- only the seed PATIENT message exists yet.
            if not await _ask_next(websocket, db, chat, history, precedent_cases):
                return
        else:
            await websocket.send_json({"type": "history", "messages": history[1:]})

        while True:
            incoming = await websocket.receive_json()
            answer = str(incoming.get("content", "")).strip()
            if not answer:
                continue

            patient_chat_service.append_message(db, session_id, ChatRole.PATIENT, answer)
            history.append({"role": "patient", "content": answer})

            if (
                patient_chat_service.question_count(db, session_id)
                >= get_settings().max_patient_intake_questions
            ):
                await _finish(websocket, db, chat, history)
                return

            if not await _ask_next(websocket, db, chat, history, precedent_cases):
                return
    except WebSocketDisconnect:
        pass


async def _ask_next(
    websocket: WebSocket, db: Session, chat, history: list[dict[str, str]], precedent_cases: list
) -> bool:
    """Returns False once the session has moved past IN_PROGRESS (the caller
    should stop looping)."""
    try:
        turn = await run_in_threadpool(
            next_intake_turn, chat.case_text or "", history, precedent_cases
        )
    except IntakeParseError:
        await _finish(websocket, db, chat, history)
        return False

    if turn.case_summary is not None:
        await _finish(websocket, db, chat, history, summary=turn.case_summary)
        return False

    patient_chat_service.append_message(db, chat.session_id, ChatRole.TWIN, turn.question)
    history.append({"role": "twin", "content": turn.question})
    await websocket.send_json({"type": "question", "content": turn.question})
    return True


async def _finish(
    websocket: WebSocket,
    db: Session,
    chat,
    history: list[dict[str, str]],
    summary: str | None = None,
) -> None:
    case_summary = summary or " ".join(
        turn["content"] for turn in history if turn["role"] == "patient"
    )
    patient = db.get(Patient, chat.patient_id)
    await run_in_threadpool(
        patient_chat_service.complete_intake, db, chat, case_summary, patient.username
    )
    await websocket.send_json({"type": "submitted_for_review"})
    await websocket.close()
