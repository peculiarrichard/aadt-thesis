from unittest.mock import patch
from uuid import uuid4

import pytest

from backend.agents.persona_agent import PersonaParseError, draft_from_persona
from backend.db.models import Case
from backend.disposition import DispositionClass


def _make_case(disposition: str) -> Case:
    return Case(
        case_id=uuid4(),
        clinician_id=uuid4(),
        transcript_or_summary="fever and chills",
        doctor_reasoning_notes="classic uncomplicated malaria",
        doctor_disposition=disposition,
    )


def test_parses_a_well_formed_response():
    precedent = [_make_case("self_care_advice")]
    response = "DISPOSITION: self-care advice\nREASONING: matches her prior case exactly."

    with patch("backend.agents.persona_agent.chat_completion", return_value=response) as mocked:
        draft = draft_from_persona("new case text", precedent)

    assert draft.disposition == DispositionClass.SELF_CARE_ADVICE
    assert "matches her prior case" in draft.reasoning
    mocked.assert_called_once()


def test_retries_once_on_malformed_response_then_succeeds():
    malformed = "I think this patient should probably just rest."
    well_formed = "DISPOSITION: urgent referral\nREASONING: red flags present."

    with patch(
        "backend.agents.persona_agent.chat_completion", side_effect=[malformed, well_formed]
    ) as mocked:
        draft = draft_from_persona("new case text", [_make_case("urgent_referral")])

    assert draft.disposition == DispositionClass.URGENT_REFERRAL
    assert mocked.call_count == 2


def test_raises_persona_parse_error_after_two_malformed_responses():
    malformed = "not in the right format at all"

    with patch(
        "backend.agents.persona_agent.chat_completion", side_effect=[malformed, malformed]
    ) as mocked:
        with pytest.raises(PersonaParseError):
            draft_from_persona("new case text", [_make_case("urgent_referral")])

    assert mocked.call_count == 2


def test_parses_disposition_case_insensitively():
    response = "disposition: URGENT REFERRAL\nreasoning: because."

    with patch("backend.agents.persona_agent.chat_completion", return_value=response):
        draft = draft_from_persona("case", [_make_case("urgent_referral")])

    assert draft.disposition == DispositionClass.URGENT_REFERRAL


def test_parses_disposition_given_as_the_enum_value():
    response = "DISPOSITION: scheduled_appointment\nREASONING: because."

    with patch("backend.agents.persona_agent.chat_completion", return_value=response):
        draft = draft_from_persona("case", [_make_case("scheduled_appointment")])

    assert draft.disposition == DispositionClass.SCHEDULED_APPOINTMENT
