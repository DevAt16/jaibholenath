import pytest
from shiva_discovery.expansion_plan import build_expansion_plan


def location(name='Agra', **overrides):
    return dict(name=name, state_name='Uttar Pradesh', district_name='Agra',
                location_type='urban_local_body', **overrides)


def test_bounded_plan_counts_pages_and_deduplicates_without_predicting_temples():
    rows = [location(), location(), location('Other'), {**location(), 'location_type': 'village'}]
    result = build_expansion_plan(rows, limit=1, max_pages=3, request_budget=20)
    assert result['eligible_unique_locations'] == 2
    assert result['selected_locations'] == 1
    assert result['duplicate_rows_removed'] == 1
    assert result['excluded_rows'] == 1
    assert result['potential_tasks'] == 9
    assert result['maximum_page_requests'] == 27
    assert result['whole_tasks_fitting_worst_case'] == 6
    assert result['worst_case_months_at_assumed_allowance'] == 2
    assert result['google_requests_sent'] == 0
    assert not result['queue_modified']


def test_scope_uncertainty_and_default_zero_budget():
    rows = [location(), {**location(), 'state_name': 'Other'},
            {**location('Ambiguous'), 'sub_district_name': 'A'},
            {**location('Ambiguous'), 'sub_district_name': 'B'}]
    result = build_expansion_plan(rows, state='Uttar Pradesh')
    assert result['selected_locations'] == 1
    assert len(result['withheld_ambiguous_groups']) == 1
    assert result['whole_tasks_fitting_worst_case'] == 0
    assert result['worst_case_months_at_assumed_allowance'] is None
    assert build_expansion_plan([], state='missing')['potential_tasks'] == 0
    with pytest.raises(ValueError):
        build_expansion_plan([{**location(), 'name': ''}])
    for kwargs in [{'limit': 0}, {'max_pages': 4}, {'request_budget': 35000}, {'location_types': ['village']}]:
        with pytest.raises(ValueError):
            build_expansion_plan([], **kwargs)


def test_pilot_prioritizes_locations_with_district_attribution():
    rows = [{**location('A missing'), 'district_name': ''}, location('Z known')]
    result = build_expansion_plan(rows, limit=1)
    assert result['locations_without_district'] == 0
    assert result['tasks'][0]['name'] == 'Z known'
