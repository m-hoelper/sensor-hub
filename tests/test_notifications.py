import pytest
from sqlalchemy import text

LOW_AIR = {"device_id": "esp-1", "co2_ppm": 700, "temperature_c": 20.5, "humidity_pct": 45.0}


@pytest.fixture()
def two_notifications(client, db_session, seed_measurements):

    db_session.execute(text("UPDATE notifications SET created_at = created_at - interval '20 minutes'"))

    response = client.post('/measurements', json=LOW_AIR)
    return response.json()


def test_seed_creates_one_notification_with_nested_measurement(client, seed_measurements):

    response = client.get('/notifications')
    body = response.json()

    assert response.status_code == 200
    assert [n['id'] for n in body] == [1]
    assert body[0]['new_state'] == 'OPEN_RECOMMENDED'
    assert body[0]['message'].startswith('Open the window')
    assert body[0]['measurement']['id'] == 7
    assert body[0]['measurement']['co2_ppm'] == 1260

    assert body[0]['sent_at'] is None
    assert body[0]['attempts'] == 0
    assert 'last_error' not in body[0]


def test_low_air_after_cooldown_closes(client, two_notifications):

    body = client.get('/notifications').json()

    assert [n['id'] for n in body] == [2, 1]  
    assert [n['new_state'] for n in body] == ['CLOSED', 'OPEN_RECOMMENDED']
    assert body[0]['measurement']['id'] == two_notifications['id']
    assert body[0]['message'].startswith('Close the window')


def test_cooldown_blocks_state_change(client, seed_measurements):

    client.post('/measurements', json=LOW_AIR)

    assert [n['id'] for n in client.get('/notifications').json()] == [1]


def test_no_notification_without_state_change(client):

    response = client.post('/measurements', json=LOW_AIR)

    assert response.status_code == 201
    assert client.get('/notifications').json() == []


@pytest.mark.parametrize(
        ['limit', 'offset', 'expected_ids'],
        [(1, 0, [2]), (1, 1, [1]), (10, 0, [2, 1]), (10, 2, [])]
)
def test_get_notifications_pagination(client, two_notifications, limit, offset, expected_ids):

    response = client.get(f'/notifications?limit={limit}&offset={offset}')

    assert response.status_code == 200
    assert [n['id'] for n in response.json()] == expected_ids


def test_notification_survives_measurement_delete(client, seed_measurements):

    response = client.delete('/measurements/7')
    assert response.status_code == 204

    response = client.get('/notifications')
    body = response.json()

    assert response.status_code == 200
    assert [n['id'] for n in body] == [1]
    assert body[0]['new_state'] == 'OPEN_RECOMMENDED'
    assert body[0]['measurement'] is None


def test_get_notifications_empty(client):

    response = client.get('/notifications')

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
        'query',
        ['limit=0', 'limit=21', 'offset=-1', 'limit=abc']
)
def test_get_notifications_invalid_query_returns_422(client, query):

    response = client.get(f'/notifications?{query}')

    assert response.status_code == 422
