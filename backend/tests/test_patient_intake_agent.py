from unittest.mock import patch
from uuid import uuid4

import pytest

from backend.agents.patient_intake_agent import IntakeParseError, _format_example, next_intake_turn
from backend.db.models import Case


def _make_case() -> Case:
    return Case(
        case_id=uuid4(),
        clinician_id=uuid4(),
        transcript_or_summary="fever and chills",
        questions_to_ask=["onset", "any prior episodes"],
        examination_or_checks="temperature and respiratory rate.",
        red_flags="stiff neck, confusion.",
        doctor_disposition="urgent_referral",
    )


def test_parses_a_question():
    response = "QUESTION: When did the fever start?"

    with patch(
        "backend.agents.patient_intake_agent.chat_completion", return_value=response
    ) as mocked:
        turn = next_intake_turn("fever", [], [_make_case()])

    assert turn.question == "When did the fever start?"
    assert turn.case_summary is None
    mocked.assert_called_once()


def test_parses_ready_to_summarize_across_multiple_lines():
    response = (
        "READY_TO_SUMMARIZE: Patient reports a 3-day fever with chills,\n"
        "no cough, no rash, worsening over the last day."
    )

    with patch("backend.agents.patient_intake_agent.chat_completion", return_value=response):
        turn = next_intake_turn("fever", [{"role": "patient", "content": "fever"}], [_make_case()])

    assert turn.question is None
    assert "3-day fever" in turn.case_summary
    assert "worsening" in turn.case_summary


def test_retries_once_on_malformed_response_then_succeeds():
    malformed = "Let me think about that."
    well_formed = "QUESTION: Any difficulty breathing?"

    with patch(
        "backend.agents.patient_intake_agent.chat_completion",
        side_effect=[malformed, well_formed],
    ) as mocked:
        turn = next_intake_turn("fever", [], [_make_case()])

    assert turn.question == "Any difficulty breathing?"
    assert mocked.call_count == 2


def test_raises_intake_parse_error_after_two_malformed_responses():
    malformed = "not in the right format at all"

    with patch(
        "backend.agents.patient_intake_agent.chat_completion",
        side_effect=[malformed, malformed],
    ) as mocked:
        with pytest.raises(IntakeParseError):
            next_intake_turn("fever", [], [_make_case()])

    assert mocked.call_count == 2


def test_format_example_weaves_workup_habits_not_literal_questions():
    case = _make_case()

    formatted = _format_example(case)

    assert "she'd ask about onset; any prior episodes" in formatted
    assert "check temperature and respiratory rate" in formatted
    assert "watch for stiff neck, confusion" in formatted


def test_format_example_returns_empty_string_when_no_workup_recorded():
    case = _make_case()
    case.questions_to_ask = None
    case.examination_or_checks = None
    case.red_flags = None

    assert _format_example(case) == ""
