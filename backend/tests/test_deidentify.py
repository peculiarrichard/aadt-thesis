"""Tests the de-identification pipeline against synthetic fake patient records
(Section 11 Phase 1) — none of the names, numbers, or addresses below are real.
"""

from backend.deidentify import deidentify_text, generate_patient_ref


def test_redacts_titled_name():
    result = deidentify_text("Mrs. Adaeze Okafor presented with fever.")

    assert "Adaeze Okafor" not in result.text
    assert "[REDACTED:NAME]" in result.text
    assert any(r.category == "NAME" for r in result.redactions)


def test_redacts_local_format_phone_number():
    result = deidentify_text("Contact number is 08031234567 for follow-up.")

    assert "08031234567" not in result.text
    assert "[REDACTED:PHONE]" in result.text


def test_redacts_international_format_phone_number():
    result = deidentify_text("Reachable on +2348031234567 after hours.")

    assert "+2348031234567" not in result.text
    assert "[REDACTED:PHONE]" in result.text


def test_phone_number_is_not_also_flagged_as_national_id():
    result = deidentify_text("Contact number is 08031234567 for follow-up.")

    categories = [r.category for r in result.redactions]
    assert categories == ["PHONE"]


def test_redacts_email():
    result = deidentify_text("Send results to patient.fake@example.com please.")

    assert "patient.fake@example.com" not in result.text
    assert "[REDACTED:EMAIL]" in result.text


def test_redacts_national_id_number():
    result = deidentify_text("NIN on file: 12345678901.")

    assert "12345678901" not in result.text
    assert "[REDACTED:NATIONAL_ID]" in result.text


def test_redacts_date():
    result = deidentify_text("Date of birth: 14/03/1988, seen again on 2024-01-05.")

    assert "14/03/1988" not in result.text
    assert "2024-01-05" not in result.text
    assert result.text.count("[REDACTED:DATE]") == 2


def test_redacts_address():
    result = deidentify_text("Resides at 15 Allen Avenue, comes in for review.")

    assert "Allen Avenue" not in result.text
    assert "[REDACTED:ADDRESS]" in result.text


def test_leaves_ordinary_clinical_content_untouched():
    clinical_text = (
        "Patient presents with fever, headache and photophobia for three days. "
        "No history of trauma. Blood pressure 120/80. Recommend paracetamol and review."
    )

    result = deidentify_text(clinical_text)

    assert result.text == clinical_text
    assert result.redactions == []


def test_full_synthetic_transcript_with_multiple_pii_types():
    transcript = (
        "Mrs. Adaeze Okafor, DOB 14/03/1988, phone 08031234567, "
        "email patient.fake@example.com, resides at 15 Allen Avenue. "
        "Presents with fever and headache for three days. "
        "NIN 12345678901 on file. Recommend paracetamol and review in one week."
    )

    result = deidentify_text(transcript)

    assert "Adaeze Okafor" not in result.text
    assert "08031234567" not in result.text
    assert "patient.fake@example.com" not in result.text
    assert "Allen Avenue" not in result.text
    assert "14/03/1988" not in result.text
    assert "12345678901" not in result.text
    # clinical content survives
    assert "fever and headache" in result.text
    assert "Recommend paracetamol" in result.text

    categories = {r.category for r in result.redactions}
    assert categories == {"NAME", "PHONE", "EMAIL", "ADDRESS", "DATE", "NATIONAL_ID"}


def test_generate_patient_ref_is_pseudonymous_and_unique():
    ref_one = generate_patient_ref()
    ref_two = generate_patient_ref()

    assert ref_one.startswith("PT-")
    assert ref_two.startswith("PT-")
    assert ref_one != ref_two
