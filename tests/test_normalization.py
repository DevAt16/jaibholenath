from shiva_discovery.normalization import compact_normalized, normalize_header, normalize_name


def test_normalize_name_removes_marks_punctuation_and_extra_space():
    assert normalize_name(" Śrī   Kashi-Vishwanath Mandir!! ") == "sri kashi vishwanath mandir"


def test_normalize_header_uses_underscore_keys():
    assert normalize_header("State/UT Name") == "state_ut_name"


def test_compact_normalized_removes_spaces():
    assert compact_normalized("Mahakal Eshwar") == "mahakaleshwar"
