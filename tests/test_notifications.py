import pytest

def test_get_notifications_newest_first_with_nested_measurement(client, seed_measurements):

    response = client.get('/notifications')
    body = response.json()

    assert response.status_code == 200
    assert [n['id'] for n in body] == [2, 1]
    assert [n['new_state'] for n in body] == ['OPEN_RECOMMENDED', 'CLOSED']

    assert body[0]['measurement']['id'] == 7
    assert body[0]['measurement']['co2_ppm'] == 1260
    assert body[1]['measurement']['id'] == 1
    assert body[1]['measurement']['co2_ppm'] == 420

    assert body[0]['sent_at'] is None
    assert body[0]['attempts'] == 0
    assert 'last_error' not in body[0]


@pytest.mark.parametrize(
        ['limit', 'offset', 'expected_ids'],
        [(1, 0, [2]), (1, 1, [1]), (10, 0, [2, 1]), (10, 2, [])]
)
def test_get_notifications_pagination(client, seed_measurements, limit, offset, expected_ids):

    response = client.get(f'/notifications?limit={limit}&offset={offset}')

    assert response.status_code == 200
    assert [n['id'] for n in response.json()] == expected_ids


def test_notification_survives_measurement_delete(client, db_session, seed_measurements):

    response = client.delete('/measurements/1')
    assert response.status_code == 204

    response = client.get('/notifications')
    body = response.json()

    assert response.status_code == 200
    assert [n['id'] for n in body] == [2, 1]
    assert body[1]['new_state'] == 'CLOSED'
    assert body[1]['measurement'] is None
    assert body[0]['measurement']['id'] == 7


def test_get_notifications_empty(client):

    response = client.get('/notifications')

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
        'query',
        [('limit=0'), ('limit=21'), ('offset=-1'), ('limit=abc')]
)
def test_get_notifications_invalid_query_returns_422(client, query):

    response = client.get(f'/notifications?{query}')

    assert response.status_code == 422
