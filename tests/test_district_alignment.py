from shiva_discovery.district_alignment import (
    build_district_alignment,
    canonical_district_name,
    canonical_state_name,
)


def test_canonical_names_remove_noise_and_common_synonyms():
    assert canonical_state_name("The Dadra And Nagar Haveli And Daman And Diu") == (
        "dadra and nagar haveli and daman and diu"
    )
    assert canonical_district_name("Khargone (West Nimar)") == "khargone"
    assert canonical_district_name("Jaipur (Gramin)") == "jaipur rural"
    assert canonical_district_name("Purbi Champaran") == "east champaran"
    assert canonical_district_name("North East Delhi", state_name="Delhi") == "north east"
    assert canonical_district_name("Lakshadweep District", state_name="Lakshadweep") == "lakshadweep"


def test_alignment_marks_exact_and_canonical_matches_auto():
    lgd_rows = [
        {
            "state_name": "Bihar",
            "district_name": "Purbi Champaran",
            "state_lgd_code": "10",
            "district_lgd_code": "213",
            "source": "lgd",
        },
        {
            "state_name": "Madhya Pradesh",
            "district_name": "Khargone (West Nimar)",
            "state_lgd_code": "23",
            "district_lgd_code": "414",
            "source": "lgd",
        },
    ]
    db_rows = [
        {
            "id": 1,
            "state_name": "Bihar",
            "district_name": "East Champaran",
            "name": "East Champaran",
            "district_lgd_code": None,
            "source": "manual",
        },
        {
            "id": 2,
            "state_name": "Madhya Pradesh",
            "district_name": "Khargone",
            "name": "Khargone",
            "district_lgd_code": None,
            "source": "manual",
        },
    ]

    matches = build_district_alignment(lgd_rows=lgd_rows, db_rows=db_rows)
    lgd_matches = [match for match in matches if match.lgd_row]

    assert [match.match_status for match in lgd_matches] == ["auto", "auto"]
    assert {match.match_method for match in lgd_matches} == {"canonical_name"}


def test_alignment_leaves_unclear_rows_for_review_or_missing():
    lgd_rows = [
        {
            "state_name": "Arunachal Pradesh",
            "district_name": "Papum Pare",
            "state_lgd_code": "12",
            "district_lgd_code": "237",
            "source": "lgd",
        }
    ]
    db_rows = [
        {
            "id": 1,
            "state_name": "Arunachal Pradesh",
            "district_name": "Itanagar Capital Complex",
            "name": "Itanagar Capital Complex",
            "district_lgd_code": None,
            "source": "manual",
        }
    ]

    matches = build_district_alignment(lgd_rows=lgd_rows, db_rows=db_rows)
    lgd_match = next(match for match in matches if match.lgd_row)

    assert lgd_match.match_status in {"review", "missing_in_db"}
    assert lgd_match.match_status != "auto"
