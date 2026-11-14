import pytest
from datetime import datetime, timedelta, timezone
from conftest import batch_of
from sqlalchemy import text

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

    co2 = [1490, 1420]

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

    response = client.post('/measurements', json=batch_of(payload))

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
    response = no_header_client.post('/measurements', json=batch_of(payload), headers=header)

    assert response.status_code == expected_status

def test_get_co2_stats(client, seed_measurements):

    response = client.get('/measurements/stats?device_id=esp-1')
    body = response.json()

    status = {'count': 4, 'max_co2': 1340, 'min_co2': 420, 'avg_co2': 897.5}

    for s in status: 
        assert body[s] == status[s]




# ---------------------------------------------------------------------------
# POST /measurements: one batch of 1–500 readings from one device (step 11e)
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
VALUES = {'co2_ppm': 600, 'temperature_c': 21.0, 'humidity_pct': 45.0}


def reading(seconds_ago: float = 0, **overrides) -> dict:
    return {**VALUES, 'created_at': (NOW - timedelta(seconds=seconds_ago)).isoformat(), **overrides}

def batch(*readings, device_id='esp-1') -> dict:
    return {'device_id': device_id, 'measurements': list(readings)}

def count_rows(client, device_id='esp-1') -> int:
    return client.get(f'/measurements/stats?device_id={device_id}').json()['count']


def test_post_batch_returns_counts_and_stores_device_time(client):

    sent = batch(reading(seconds_ago=60), reading(seconds_ago=30, co2_ppm=650))

    response = client.post('/measurements', json=sent)

    assert response.status_code == 201
    assert response.json() == {'inserted': 2, 'duplicates': 0}

    latest = client.get('/measurements/latest?device_id=esp-1').json()
    assert latest['co2_ppm'] == 650
    assert latest['device_id'] == 'esp-1'
    assert datetime.fromisoformat(latest['created_at']) == NOW - timedelta(seconds=30)   # device time, not server time


def test_resent_batch_counts_duplicates_and_stores_nothing(client):

    sent = batch(reading(seconds_ago=60), reading(seconds_ago=30))

    client.post('/measurements', json=sent)
    response = client.post('/measurements', json=sent)            # lost 201 → the ESP32 sends the same chunk again

    assert response.status_code == 201                            # still success, so the device drops the chunk
    assert response.json() == {'inserted': 0, 'duplicates': 2}
    assert count_rows(client) == 2


def test_partly_known_batch_inserts_only_new_readings(client):

    client.post('/measurements', json=batch(reading(seconds_ago=60)))

    response = client.post('/measurements', json=batch(reading(seconds_ago=60), reading(seconds_ago=30)))

    assert response.json() == {'inserted': 1, 'duplicates': 1}
    assert count_rows(client) == 2


def test_same_time_on_another_device_is_not_a_duplicate(client):

    client.post('/measurements', json=batch(reading(seconds_ago=30), device_id='esp-1'))
    response = client.post('/measurements', json=batch(reading(seconds_ago=30), device_id='esp-2'))

    assert response.json() == {'inserted': 1, 'duplicates': 0}


def test_epoch_seconds_from_the_esp32_are_accepted_as_utc(client):

    epoch = int(NOW.timestamp())

    response = client.post('/measurements', json=batch({**VALUES, 'created_at': epoch}))

    assert response.status_code == 201
    latest = client.get('/measurements/latest').json()
    assert datetime.fromisoformat(latest['created_at']) == datetime.fromtimestamp(epoch, timezone.utc)


def test_500_readings_are_accepted(client):

    response = client.post('/measurements', json=batch(*[reading(seconds_ago=30 * i) for i in range(500)]))

    assert response.status_code == 201
    assert response.json() == {'inserted': 500, 'duplicates': 0}


@pytest.mark.parametrize(
        'body',
        [batch(),                                                          # empty list
         batch(*[reading(seconds_ago=30 * i) for i in range(501)]),        # one over the limit
         batch(reading(created_at='2026-11-14T12:00:00')),                 # naive time → ambiguous
         batch({**VALUES}),                                                # created_at missing
         {'measurements': [reading()]},                                    # device_id missing
         {'device_id': 'esp-1', 'measurements': reading()}]                # a single object, not a list
)
def test_invalid_batch_returns_422_and_stores_nothing(client, body):

    response = client.post('/measurements', json=body)

    assert response.status_code == 422
    assert client.get('/measurements').json() == []


def test_backfilled_old_reading_does_not_become_latest(client, seed_measurements):

    client.post('/measurements', json=batch(reading(seconds_ago=3600), device_id='esp-3'))   # gets id 11 …

    latest = client.get('/measurements/latest').json()
    assert latest['id'] == 10                                                                 # … but is older


def test_backfill_never_creates_a_notification(client):

    old_and_high = batch(*[reading(seconds_ago=3600 + 30 * i, co2_ppm=2500) for i in range(10)])

    response = client.post('/measurements', json=old_and_high)

    assert response.json()['inserted'] == 10
    assert client.get('/notifications').json() == []


def test_rules_judge_only_the_newest_reading_of_a_batch(client):

    # an old spike, then fresh air: only the newest reading describes the room now
    response = client.post('/measurements', json=batch(reading(seconds_ago=60, co2_ppm=2500),
                                                       reading(seconds_ago=0, co2_ppm=500)))

    assert response.status_code == 201
    assert client.get('/notifications').json() == []


def test_resend_does_not_create_a_second_notification(client, db_session):

    high = batch(reading(seconds_ago=0, co2_ppm=2500))

    client.post('/measurements', json=high)
    db_session.execute(text("UPDATE notifications SET created_at = created_at - interval '20 minutes'"))  # past the cooldown
    client.post('/measurements', json=high)

    notifications = client.get('/notifications').json()
    assert [n['new_state'] for n in notifications] == ['OPEN_RECOMMENDED']
