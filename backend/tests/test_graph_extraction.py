from backend.ingestion.graph_extraction import extract_condition_relations


def test_extracts_symptoms_and_recommendations_for_a_condition():
    lines = [
        "CHAPTER 1: ALIMENTARY TRACT",
        "HAEMORRHOIDS",
        "Introduction",
        "A common condition of the anal canal.",
        "Clinical features",
        "Rectal bleeding",
        "Anal itching",
        "Differential diagnoses",
        "Anal fissure",
        "Treatment objectives",
        "Relieve symptoms",
        "Drug treatment",
        "Topical corticosteroids",
        "Caution",
        "Avoid in pregnancy without review",
    ]

    results = extract_condition_relations(lines)

    assert len(results) == 1
    result = results[0]
    assert result.condition == "HAEMORRHOIDS"
    assert result.symptoms == ["Rectal bleeding", "Anal itching"]
    assert result.recommendations == ["Relieve symptoms", "Topical corticosteroids"]


def test_multiple_conditions_do_not_bleed_into_each_other():
    lines = [
        "AMOEBIASIS",
        "Clinical features",
        "Bloody diarrhoea",
        "PANCREATITIS",
        "Clinical features",
        "Severe abdominal pain",
    ]

    results = extract_condition_relations(lines)

    assert [r.condition for r in results] == ["AMOEBIASIS", "PANCREATITIS"]
    assert results[0].symptoms == ["Bloody diarrhoea"]
    assert results[1].symptoms == ["Severe abdominal pain"]


def test_headings_with_no_labeled_content_are_dropped():
    lines = ["FOREWORD", "Some unlabeled prose that follows the heading."]

    results = extract_condition_relations(lines)

    assert results == []


def test_content_before_any_heading_is_ignored():
    lines = ["Clinical features", "orphaned line with no condition"]

    results = extract_condition_relations(lines)

    assert results == []


def test_empty_input_returns_no_results():
    assert extract_condition_relations([]) == []
