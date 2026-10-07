"""Mocked LLM layer throughout -- no real Ollama call."""

from unittest.mock import patch

from backend.agents.pii_review_agent import PiiReviewResult
from backend.services.privacy_scan import scan_fields_for_privacy_risk, scan_for_privacy_risk


def _mock_llm(flagged: bool, details: str | None = None):
    return patch(
        "backend.services.privacy_scan.review_for_identifiability",
        return_value=PiiReviewResult(flagged=flagged, details=details),
    )


def test_clean_text_is_not_flagged_for_review():
    with _mock_llm(flagged=False):
        result = scan_for_privacy_risk("A 40-year-old woman with fever and chills.")

    assert result.redaction_summary == {}
    assert result.llm_flagged is False
    assert result.requires_review is False


def test_regex_redaction_alone_triggers_review():
    with _mock_llm(flagged=False):
        result = scan_for_privacy_risk("Call Dr. Jane Okafor on 08012345678.")

    assert result.redaction_summary  # NAME and/or PHONE caught
    assert "[REDACTED:" in result.text
    assert result.requires_review is True


def test_llm_flag_alone_triggers_review_even_with_no_regex_hits():
    with _mock_llm(flagged=True, details="Named clinic."):
        result = scan_for_privacy_risk("Seen at a specific clinic, no names given.")

    assert result.redaction_summary == {}
    assert result.llm_flagged is True
    assert result.llm_flag_details == "Named clinic."
    assert result.requires_review is True


def test_llm_review_runs_on_the_already_regex_redacted_text():
    """The LLM shouldn't need to re-discover what regex already caught --
    confirms the LLM call receives the redacted text, not the raw original."""
    with patch(
        "backend.services.privacy_scan.review_for_identifiability",
        return_value=PiiReviewResult(flagged=False, details=None),
    ) as mocked:
        scan_for_privacy_risk("Contact john@example.com for details.")

    called_with_text = mocked.call_args[0][0]
    assert "john@example.com" not in called_with_text
    assert "[REDACTED:EMAIL]" in called_with_text


def test_scan_fields_redacts_every_free_text_field_independently():
    with _mock_llm(flagged=False):
        redacted, result = scan_fields_for_privacy_risk(
            {
                "transcript_or_summary": "Fever and chills.",
                "factors_against_referral": "Discussed with Dr. Jane Okafor, agreed to monitor.",
                "doctor_disposition": "self_care_advice",  # not a free-text field, left alone
            }
        )

    assert redacted["transcript_or_summary"] == "Fever and chills."
    assert "[REDACTED:NAME]" in redacted["factors_against_referral"]
    assert redacted["doctor_disposition"] == "self_care_advice"
    assert result.redaction_summary == {"NAME": 1}


def test_scan_fields_makes_exactly_one_llm_call_regardless_of_field_count():
    with _mock_llm(flagged=False) as mocked:
        scan_fields_for_privacy_risk(
            {
                "transcript_or_summary": "a",
                "initial_impression": "b",
                "factors_toward_referral": "c",
                "general_rule": "d",
            }
        )

    mocked.assert_called_once()


def test_scan_fields_with_no_free_text_present_does_not_call_the_llm():
    with _mock_llm(flagged=False) as mocked:
        redacted, result = scan_fields_for_privacy_risk({"doctor_disposition": "self_care_advice"})

    mocked.assert_not_called()
    assert result.llm_flagged is False
    assert redacted == {"doctor_disposition": "self_care_advice"}
