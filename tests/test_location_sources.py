from shiva_discovery.location_sources import (
    append_unique_location_rows,
    normalize_census_town_rows,
    normalize_lgd_district_rows,
    normalize_lgd_local_body_rows,
    normalize_lgd_sub_district_rows,
)


def test_normalize_lgd_district_rows_filters_state_and_maps_codes():
    rows = [
        {
            "stateNameEnglish": "Uttar Pradesh",
            "stateCode": "9",
            "districtNameEnglish": "Agra",
            "districtCode": "118",
        },
        {
            "stateNameEnglish": "Maharashtra",
            "stateCode": "27",
            "districtNameEnglish": "Pune",
            "districtCode": "521",
        },
    ]

    normalized, stats = normalize_lgd_district_rows(rows, state_filter="Uttar Pradesh")

    assert stats.read_rows == 2
    assert stats.emitted_rows == 1
    assert normalized == [
        {
            "location_type": "district",
            "name": "Agra",
            "state_name": "Uttar Pradesh",
            "district_name": "Agra",
            "sub_district_name": "",
            "state_lgd_code": "9",
            "district_lgd_code": "118",
            "sub_district_lgd_code": "",
            "village_lgd_code": "",
            "source": "lgd",
        }
    ]


def test_normalize_lgd_local_body_rows_keeps_urban_and_skips_rural():
    rows = [
        {
            "stateNameEnglish": "Uttar Pradesh",
            "districtNameEnglish": "Agra",
            "localBodyNameEnglish": "Agra Municipal Corporation",
            "localBodyCode": "1001",
            "localBodyTypeName": "Municipal Corporation",
        },
        {
            "stateNameEnglish": "Uttar Pradesh",
            "districtNameEnglish": "Agra",
            "localBodyNameEnglish": "Some Gram Panchayat",
            "localBodyCode": "2001",
            "localBodyTypeName": "Gram Panchayat",
        },
    ]

    normalized, stats = normalize_lgd_local_body_rows(rows)

    assert stats.read_rows == 2
    assert stats.emitted_rows == 1
    assert normalized[0]["location_type"] == "urban_local_body"
    assert normalized[0]["name"] == "Agra Municipal Corporation"
    assert normalized[0]["village_lgd_code"] == ""


def test_normalize_lgd_local_body_rows_dedupes_coverage_and_uses_lookup():
    rows = [
        {
            "stateNameEnglish": "Uttar Pradesh",
            "localBodyCode": "249062",
            "localBodyNameEnglish": "Agra",
            "localBodyTypeName": "Municipal Corporations",
            "entityCode": "766",
            "entityName": "Agra",
            "entityType": "Subistrict",
        },
        {
            "stateNameEnglish": "Uttar Pradesh",
            "localBodyCode": "249062",
            "localBodyNameEnglish": "Agra",
            "localBodyTypeName": "Municipal Corporations",
            "entityCode": "123456",
            "entityName": "Covered Village",
            "entityType": "Village",
        },
    ]
    lookup = {
        "766": {
            "district_name": "Agra",
            "district_lgd_code": "118",
            "sub_district_name": "Agra",
        }
    }

    normalized, stats = normalize_lgd_local_body_rows(rows, sub_district_lookup=lookup)

    assert stats.read_rows == 2
    assert stats.emitted_rows == 1
    assert normalized[0]["name"] == "Agra"
    assert normalized[0]["district_name"] == "Agra"
    assert normalized[0]["district_lgd_code"] == "118"
    assert normalized[0]["sub_district_name"] == "Agra"


def test_normalize_lgd_sub_district_rows_supports_data_gov_headers():
    rows = [
        {
            "state_code": "9",
            "state_name_english": "Uttar Pradesh",
            "district_code": "118",
            "district_name_english": "Agra",
            "subdistrict_code": "766",
            "subdistrict_name_english": "Agra",
        }
    ]

    normalized, stats = normalize_lgd_sub_district_rows(rows)

    assert stats.emitted_rows == 1
    assert normalized[0]["location_type"] == "sub_district"
    assert normalized[0]["name"] == "Agra"
    assert normalized[0]["district_name"] == "Agra"
    assert normalized[0]["sub_district_lgd_code"] == "766"


def test_normalize_census_town_rows_dedupes_wards_and_skips_rural_rows():
    rows = [
        {
            "State": "Uttar Pradesh",
            "District": "Agra",
            "Sub-District": "Kiraoli",
            "Town": "Achhnera",
            "Urban/Rural": "Urban",
            "Ward": "Ward 1",
        },
        {
            "State": "Uttar Pradesh",
            "District": "Agra",
            "Sub-District": "Kiraoli",
            "Town": "Achhnera",
            "Urban/Rural": "Urban",
            "Ward": "Ward 2",
        },
        {
            "State": "Uttar Pradesh",
            "District": "Agra",
            "Sub-District": "Kiraoli",
            "Town": "Rural Example",
            "Urban/Rural": "Rural",
        },
    ]

    normalized, stats = normalize_census_town_rows(rows, state_filter="Uttar Pradesh")

    assert stats.read_rows == 3
    assert stats.emitted_rows == 1
    assert stats.duplicate_rows == 1
    assert normalized[0]["location_type"] == "town"
    assert normalized[0]["name"] == "Achhnera"
    assert normalized[0]["source"] == "census_2011"


def test_append_unique_location_rows_preserves_existing_and_appends_new(tmp_path):
    path = tmp_path / "locations.csv"
    path.write_text(
        "\n".join(
            [
                "location_type,name,state_name,district_name,sub_district_name,state_lgd_code,district_lgd_code,sub_district_lgd_code,village_lgd_code,source",
                "town,Achhnera,Uttar Pradesh,Agra,,,,,,manual_pilot",
            ]
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "location_type": "town",
            "name": "Achhnera",
            "state_name": "Uttar Pradesh",
            "district_name": "Agra",
            "sub_district_name": "",
            "state_lgd_code": "",
            "district_lgd_code": "",
            "sub_district_lgd_code": "",
            "village_lgd_code": "",
            "source": "census_2011",
        },
        {
            "location_type": "town",
            "name": "Fatehpur Sikri",
            "state_name": "Uttar Pradesh",
            "district_name": "Agra",
            "sub_district_name": "",
            "state_lgd_code": "",
            "district_lgd_code": "",
            "sub_district_lgd_code": "",
            "village_lgd_code": "",
            "source": "census_2011",
        },
    ]

    appended = append_unique_location_rows(path, rows)

    assert appended == 1
    assert "Fatehpur Sikri" in path.read_text(encoding="utf-8")
