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


def test_devanagari_shiva_names_from_pilot_are_high_confidence():
    for name in ("शिव मंदिर अछनेरा", "प्राचीन महादेव मंदिर", "वनखंडी शिव मंदिर",
                 "सोमेश्वर महादेव मन्दिर"):
        assert classify_candidate_name(name).confidence == "high"
    assert classify_candidate_name("Siv mandir").confidence == "high"


def test_shiva_house_names_from_pilot_need_manual_review():
    for name in ("Shiva home", "Shiva house golu", "Shiva ka house kiraoli agra"):
        result = classify_candidate_name(name)
        assert result.confidence == "low"
        assert "non-temple venue" in result.classification_reason
    assert classify_candidate_name("Shiva Temple near my house").confidence == "high"
