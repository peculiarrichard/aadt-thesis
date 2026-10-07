"""Mocked LLM client throughout -- no real Ollama call, per explicit
instruction not to run LLM calls on this machine anymore."""

import json
from unittest.mock import patch

from backend.agents.pii_review_agent import PiiReviewResult, review_for_identifiability

_NOT_FLAGGED = json.dumps({"flagged": False, "details": None})
_FLAGGED = json.dumps({"flagged": True, "details": "References a named clinic."})


def test_parses_a_not_flagged_response():
    with patch(
        "backend.agents.pii_review_agent.chat_completion", return_value=_NOT_FLAGGED
    ) as mocked:
        result = review_for_identifiability("A 40-year-old woman with fever and chills.")

    assert result == PiiReviewResult(flagged=False, details=None)
    mocked.assert_called_once()


def test_parses_a_flagged_response_with_details():
    with patch("backend.agents.pii_review_agent.chat_completion", return_value=_FLAGGED):
        result = review_for_identifiability("Saw this at St. Example Clinic last week.")

    assert result.flagged is True
    assert "clinic" in result.details.lower()


def test_strips_markdown_code_fences():
    fenced = f"```json\n{_FLAGGED}\n```"
    with patch("backend.agents.pii_review_agent.chat_completion", return_value=fenced):
        result = review_for_identifiability("some text")

    assert result.flagged is True


def test_retries_once_on_malformed_response_then_succeeds():
    with patch(
        "backend.agents.pii_review_agent.chat_completion",
        side_effect=["not json", _NOT_FLAGGED],
    ) as mocked:
        result = review_for_identifiability("some text")

    assert result.flagged is False
    assert mocked.call_count == 2


def test_fails_safe_as_flagged_after_two_malformed_responses():
    """Unlike the structuring agent (which falls back to "doctor fills it in
    herself"), a privacy check that can't confirm cleanliness must flag, not
    silently pass -- the one place "fail open" would be the wrong default."""
    with patch(
        "backend.agents.pii_review_agent.chat_completion",
        side_effect=["not json", "still not json"],
    ) as mocked:
        result = review_for_identifiability("some text")

    assert result.flagged is True
    assert result.details is not None
    assert mocked.call_count == 2
