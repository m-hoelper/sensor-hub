import pytest

def test_create_measurement_returns_201_with_id(client):

    payload = {
        'device_id': 'esp-2',
        'co2_ppm': 1500,
        'temperature_c': 26.0,
        'humidity_pct': 30.0,
    }

    response = client.post('/measurements', json= payload)
    body = response.json()

    assert response.status_code == 201

    assert 'id' in body
    assert 'created_at' in body 
    for c in payload:
        assert payload[c] == body[c]

def test_get_empty_mesurement_data(client):

    response = client.get('/measurements')

    body = response.json()

    assert response.status_code == 200
    assert body == []

def test_get_mesurement_data_beyond_limit(client):

    response = client.get('/measurements?limit=30')

    assert response.status_code == 422

def test_get_latest_empty_data(client):

    response = client.get('/measurements/latest')

    assert response.status_code == 404

def test_seed_data(client, seed_measurements):
    
    # test 1
    response = client.get('/measurements?device_id=esp-3')
    body = response.json()

    assert len(body) == 3
    assert response.status_code == 200

    # test 2 
    response = client.get('/measurements?limit=15')
    body = response.json()

    assert len(body) == 10
    assert response.status_code == 200

    # test 3 
    response = client.get('/measurements/latest?device_id=esp-2')
    body = response.json()

    test_data = {"device_id": "esp-2", "co2_ppm": 1420, "temperature_c": 18.7, "humidity_pct": 32.0}
    for key in test_data:
        assert test_data[key] == body[key]

    # test 4
    response = client.get('/measurements/?limit=2')
    body = response.json()

    co2 = [1420, 1490]

    for i,n in enumerate(co2):
        assert n == body[i]['co2_ppm']

@pytest.mark.parametrize(
        ['measurement_id', 'excpected_status'],
        [('abc', 422), (-3, 422), (0, 422), (5, 200), (12, 404)]
    )

def test_measurement_ids(client, seed_measurements, measurement_id, excpected_status):

    response = client.get(f'/measurements/{measurement_id}')
    assert response.status_code == excpected_status

@pytest.mark.parametrize(
        ['field', 'value'],
        [('device_id', ''), ('device_id', 'a'*60), ('co2_ppm', -20), ('co2_ppm', 50_000), ('temperature_c', -20), ('temperature_c', 100), ('humidity_pct', -1), ('humidity_pct', 101)]
        )

def test_create_measurement_invalid_field_returns_422(client, field, value):

    payload = {"device_id": "esp-1", "co2_ppm": 420,  "temperature_c": 19.5, "humidity_pct": 35.0}

    payload[field] = value

    response = client.post('/measurements/', json= payload)

    assert response.status_code == 422

@pytest.mark.parametrize(
        ['measurement_id', 'expected_delete_status', 'expected_get_status'],
        [(8, 204, 404), (9, 204, 404), (-1, 422, 422), (24, 404, 404)]
)
def test_delete_measurement(client, seed_measurements, measurement_id, expected_delete_status, expected_get_status):

    response = client.delete(f'/measurements/{measurement_id}')

    assert response.status_code == expected_delete_status

    response = client.get(f'/measurements/{measurement_id}')
    assert response.status_code == expected_get_status

@pytest.mark.parametrize(
        ['offset', 'limit', 'length'],
        [(9,10,1), (2,5,5), (2,15,8), (10,10,0)]
        )

def test_get_measurements_with_offset_and_limit(client, seed_measurements, offset, limit, length):

    response = client.get(f'/measurements?limit={limit}&offset={offset}')
    body = response.json()

    assert len(body) == length

@pytest.mark.parametrize(
        ['header', 'expected_status'],
        [({'X-Api-Key': 'test-key'}, 201), ({'X-Api-Key': 'test'}, 401), ({}, 401)]
)

def test_auth_header(no_header_client, header, expected_status):

    payload = {"device_id": "esp-1", "co2_ppm": 420,  "temperature_c": 19.5, "humidity_pct": 35.0}
    response = no_header_client.post('/measurements', json=payload, headers=header)

    assert response.status_code == expected_status
