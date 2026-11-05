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

    assert response.status_code == 400

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
        [('abc', 422), (-3, 400), (0, 400), (5, 200), (12, 404)]
    )

def test_invalid_ids(client, seed_measurements, measurement_id, excpected_status):

    response = client.get(f'/measurements/{measurement_id}')
    assert response.status_code == excpected_status






    



