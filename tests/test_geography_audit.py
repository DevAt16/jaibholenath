from shiva_discovery.geography_audit import audit_geography
from shiva_discovery.queries import build_search_query


def _row(place_id, address, lat, lon):
    location = dict(name='Achhnera', location_type='urban_local_body', state_name='Uttar Pradesh',
                    district_name='Agra', sub_district_name='Kiraoli')
    return {'google_place_id': place_id, 'discovered_name': place_id, 'discovered_address': address,
            'latitude': str(lat), 'longitude': str(lon), 'state': 'Uttar Pradesh', 'district': 'Agra',
            'source_query': build_search_query('Shiva temple', location)}


def test_flags_distant_and_other_state_addresses_without_changing_attribution():
    location = dict(name='Achhnera', location_type='urban_local_body', state_name='Uttar Pradesh',
                    district_name='Agra', sub_district_name='Kiraoli')
    rows = [_row(f'local-{n}', 'Main St, Achhnera, Uttar Pradesh 283101', 27.18, 77.75)
            for n in range(3)]
    rows.append(_row('distant', 'Temple Rd, Jaipur, Rajasthan 302001', 26.91, 75.79))
    result = audit_geography(rows, [location], {'Uttar Pradesh', 'Rajasthan'})
    flagged = result['records'][0]
    assert flagged['query_district'] == 'Agra'
    assert flagged['address_state_hint'] == 'rajasthan'
    assert flagged['review_priority'] == 'high'
    assert 'address_names_other_state' in flagged['flags']
    assert 'over_50km_from_inferred_locality_anchor' in flagged['flags']
    assert result['priority_counts'] == {'routine': 3, 'high': 1}


def test_missing_anchor_or_unnamed_locality_stays_uncertain():
    location = dict(name='Achhnera', location_type='urban_local_body', state_name='Uttar Pradesh',
                    district_name='Agra', sub_district_name='Kiraoli')
    result = audit_geography([_row('one', 'Somewhere, Uttar Pradesh 283101', 27.18, 77.75)],
                             [location], {'Uttar Pradesh'})
    assert result['query_locality_anchors'] == {}
    assert result['records'][0]['distance_from_inferred_locality_km'] == ''
    assert result['records'][0]['review_priority'] == 'medium'
