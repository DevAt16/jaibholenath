from shiva_discovery.queries import build_search_query, eligible_location_types


def test_build_district_search_query():
    location = {
        "name": "Pune",
        "location_type": "district",
        "state_name": "Maharashtra",
        "district_name": "Pune",
    }

    assert build_search_query("Shiva temple", location) == (
        "Shiva temple in Pune district, Maharashtra, India"
    )


def test_build_town_search_query_dedupes_location_parts():
    location = {
        "name": "Alandi",
        "location_type": "town",
        "state_name": "Maharashtra",
        "district_name": "Pune",
        "sub_district_name": "",
    }

    assert build_search_query("Mahadev Mandir", location) == (
        "Mahadev Mandir in Alandi, Pune, Maharashtra, India"
    )


def test_default_eligible_locations_do_not_include_villages_or_cities():
    assert eligible_location_types() == ("district", "town", "urban_local_body")
    assert eligible_location_types(include_cities=True, include_villages=True) == (
        "district",
        "town",
        "urban_local_body",
        "city",
        "village",
    )


def test_district_only_eligible_locations_exclude_default_expansion_types():
    assert eligible_location_types(district_only=True) == ("district",)
    assert eligible_location_types(
        district_only=True,
        include_cities=True,
        include_villages=True,
    ) == ("district",)
