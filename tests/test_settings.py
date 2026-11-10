import pytest

def test_get_thresholds_returns_defaults(client, default_thresholds):
    response = client.get('/settings/thresholds')

    assert response.status_code == 200
    assert response.json() == default_thresholds

def test_put_replaces_all_fields(client, default_thresholds):

    payload = {
        "co2_open_ppm": 1300,
        "co2_close_ppm": 900,
        "co2_max_ppm": 2500,
        "humidity_open_pct": 70.0,
        "humidity_close_pct": 60.0,
        "humidity_min_pct": 25.0,
        "cooldown_min": 10,
    }

    response = client.put('/settings/thresholds', json=payload)

    assert response.status_code == 200
    assert response.json() == payload

    response = client.get('/settings/thresholds')

    assert response.status_code == 200
    assert response.json() != default_thresholds
    assert response.json() == payload

@pytest.mark.parametrize(
        'field',
        ['co2_open_ppm', 'co2_close_ppm', 'co2_max_ppm', 'humidity_open_pct', 'humidity_close_pct', 'humidity_min_pct', 'cooldown_min']
)

def test_put_missing_field_returns_422(client, default_thresholds, field):

    del default_thresholds[field]

    response = client.put('/settings/thresholds', json=default_thresholds)
    assert response.status_code == 422

@pytest.mark.parametrize(
        'changes',
        [{'co2_close_ppm': 1300, 'co2_open_ppm': 800},
         {'humidity_close_pct':70, 'humidity_open_pct':60},
         {'humidity_min_pct':70, 'humidity_close_pct':60},
         {'co2_max_ppm': 1200},                         # max == open
         {'co2_open_ppm': 2500, 'co2_close_ppm': 800},]  # open above max
)

def test_put_close_above_open_returns_422(client, default_thresholds, changes):

    default_thresholds.update(changes)

    response = client.put('/settings/thresholds', json=default_thresholds)
    assert response.status_code == 422

@pytest.mark.parametrize(
        'patch',
        [{'co2_open_ppm': 1500},
         {'co2_close_ppm': 700},
         {'co2_max_ppm': 2500},
         {'humidity_open_pct': 70.0},    
         {'humidity_close_pct': 50.0},   
         {'humidity_min_pct': 25.0},     
         {'cooldown_min': 5},]
)

def test_patch_changes_only_given_field(client, default_thresholds, patch):

    response = client.patch('/settings/thresholds', json=patch)

    default_thresholds.update(patch)

    assert response.status_code == 200
    assert response.json() == default_thresholds

    response = client.get('/settings/thresholds')

    assert response.status_code == 200
    assert response.json() == default_thresholds

@pytest.mark.parametrize(
        'patch',
        [{'co2_open_ppm': 800},
         {'co2_close_ppm': 1300},
         {'co2_open_ppm': 2000},          # open == max 2000
         {'co2_max_ppm': 1100},           # max below open 1200
         {'humidity_open_pct': 50.0},
         {'humidity_close_pct': 70.0},
         {'humidity_close_pct': 25.0},
         {'humidity_min_pct': 55.0},]    
)

def test_patch_breaking_rule_with_current_values_returns_422(client, patch):

    response = client.patch('/settings/thresholds', json=patch)

    assert response.status_code == 422


def test_patch_empty_body_changes_nothing(client, default_thresholds):

    response = client.patch('/settings/thresholds', json={})

    assert response.status_code == 200
    assert response.json() == default_thresholds

    response = client.get('/settings/thresholds')

    assert response.status_code == 200
    assert response.json() == default_thresholds

@pytest.mark.parametrize('method', ['PUT', 'PATCH'])
@pytest.mark.parametrize('headers', [{}, {'X-Api-Key': 'wrong-key'}])
def test_put_and_patch_without_key_return_401(no_header_client, default_thresholds, method, headers):

    payload = {**default_thresholds, 'cooldown_min': 5}

    response = no_header_client.request(method, '/settings/thresholds', json=payload, headers=headers)
    assert response.status_code == 401

    response = no_header_client.get('/settings/thresholds')
    assert response.json() == default_thresholds