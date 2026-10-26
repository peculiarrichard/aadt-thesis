from unittest.mock import patch
from uuid import uuid4

import pytest

from backend.agents.persona_agent import PersonaParseError, _format_example, draft_from_persona
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


def test_format_example_weaves_the_full_workup_into_one_narrative_line():
    case = _make_case("urgent_referral")
    case.initial_impression = "looked unwell from the start."
    case.questions_to_ask = ["onset", "any prior episodes"]
    case.examination_or_checks = "temperature and respiratory rate."
    case.factors_toward_referral = "danger signs present."
    case.factors_against_referral = "none noted."
    case.flip_up = "fever persists past 48 hours."
    case.flip_down = "fever settles with simple antipyretics."

    formatted = _format_example(case)

    assert "looked unwell from the start" in formatted
    assert "she'd ask about onset; any prior episodes" in formatted
    assert "check temperature and respiratory rate" in formatted
    assert "would refer if danger signs present" in formatted
    assert "would escalate further if fever persists past 48 hours" in formatted
    assert "QUESTIONS_TO_ASK:" not in formatted.upper().replace(" ", "_")


def test_parses_reasoning_that_wraps_across_multiple_lines():
    response = (
        "DISPOSITION: urgent referral\n"
        "REASONING: She'd be worried about the danger signs here.\n"
        "This matches how she handled a similar case before, where she\n"
        "referred immediately rather than waiting to see how things developed."
    )

    with patch("backend.agents.persona_agent.chat_completion", return_value=response):
        draft = draft_from_persona("case", [_make_case("urgent_referral")])

    assert draft.disposition == DispositionClass.URGENT_REFERRAL
    assert "danger signs" in draft.reasoning
    assert "referred immediately" in draft.reasoning


def test_format_example_handles_missing_workup_fields():
    case = _make_case("self_care_advice")

    formatted = _format_example(case)

    assert "Her workup: (not recorded)" in formatted
