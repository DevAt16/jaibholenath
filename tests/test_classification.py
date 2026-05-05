from shiva_discovery.classification import classify_candidate_name


def test_high_confidence_matches_shiva_terms():
    result = classify_candidate_name("Sri Kashi Vishwanath Shiva Temple")

    assert result.confidence == "high"
    assert result.confidence_score >= 0.85
    assert "high-confidence" in result.classification_reason


def test_short_terms_do_not_match_across_word_boundaries():
    result = classify_candidate_name("Kashi Vishwanath Temple")

    assert result.confidence == "high"
    assert "vishwanath" in result.classification_reason
    assert "shiv," not in result.classification_reason


def test_medium_confidence_matches_medium_terms():
    result = classify_candidate_name("Someshwar Mandir")

    assert result.confidence == "medium"
    assert 0.55 <= result.confidence_score < 0.8
    assert "someshwar" in result.classification_reason


def test_low_confidence_when_no_terms_match():
    result = classify_candidate_name("Ancient Devi Temple")

    assert result.confidence == "low"
    assert result.confidence_score == 0.2
