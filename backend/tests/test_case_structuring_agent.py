import json
from unittest.mock import patch

import pytest

from backend.agents.case_structuring_agent import (
    CaseStructuringParseError,
    draft_structured_case,
)

_WELL_FORMED = json.dumps(
    {
        "case_text": "Fever and chills for three days, RDT positive for malaria.",
        "initial_impression": "Likely uncomplicated malaria.",
        "questions_to_ask": ["Duration of fever?", "Any danger signs?"],
        "examination_or_checks": "Temperature, hydration status.",
        "factors_toward_referral": None,
        "factors_against_referral": "No danger signs present.",
        "flip_up": "Development of jaundice or seizures.",
        "flip_down": None,
        "red_flags": None,
        "confidence": "Fairly confident.",
        "general_rule": "Uncomplicated malaria with no danger signs can be managed at home.",
        "disposition": "self-care advice",
        "disposition_reason": "No danger signs, positive RDT, classic presentation.",
    }
)


def test_parses_a_well_formed_json_response():
    with patch(
        "backend.agents.case_structuring_agent.chat_completion", return_value=_WELL_FORMED
    ) as mocked:
        draft = draft_structured_case("raw transcript text")

    assert draft.disposition == "self-care advice"
    assert draft.questions_to_ask == ["Duration of fever?", "Any danger signs?"]
    assert draft.factors_toward_referral is None
    mocked.assert_called_once()


def test_strips_markdown_code_fences():
    fenced = f"```json\n{_WELL_FORMED}\n```"
    with patch("backend.agents.case_structuring_agent.chat_completion", return_value=fenced):
        draft = draft_structured_case("raw transcript text")

    assert draft.case_text.startswith("Fever and chills")


def test_retries_once_on_malformed_response_then_succeeds():
    malformed = "not json at all"
    with patch(
        "backend.agents.case_structuring_agent.chat_completion",
        side_effect=[malformed, _WELL_FORMED],
    ) as mocked:
        draft = draft_structured_case("raw transcript text")

    assert draft.disposition == "self-care advice"
    assert mocked.call_count == 2


def test_raises_after_two_malformed_responses():
    malformed = "still not json"
    with patch(
        "backend.agents.case_structuring_agent.chat_completion",
        side_effect=[malformed, malformed],
    ) as mocked:
        with pytest.raises(CaseStructuringParseError):
            draft_structured_case("raw transcript text")

    assert mocked.call_count == 2


def test_unknown_disposition_label_becomes_none_not_a_parse_failure():
    bad_disposition = json.dumps({**json.loads(_WELL_FORMED), "disposition": "not a real label"})
    with patch(
        "backend.agents.case_structuring_agent.chat_completion", return_value=bad_disposition
    ):
        draft = draft_structured_case("raw transcript text")

    assert draft.disposition is None
    assert draft.case_text  # the rest of the extraction still succeeded
