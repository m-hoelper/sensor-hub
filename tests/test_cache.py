import redis
from sqlalchemy import text

import sensor_hub.cache as cache_module
import sensor_hub.main as main
from sensor_hub.services import TTL_SECONDS, newest_key

# seed_measurements: latest overall = id 10 (esp-3), esp-1 = id 8, esp-2 = id 9
NEW_ESP1 = {"device_id": "esp-1", "co2_ppm": 600, "temperature_c": 21.0, "humidity_pct": 45.0}


class BrokenCache:
    """Redis is down: every command fails like the real client would."""

    def get(self, key):
        raise redis.exceptions.ConnectionError('connection refused')

    def set(self, key, value, ex=None):
        raise redis.exceptions.ConnectionError('connection refused')

    def delete(self, *keys):
        raise redis.exceptions.ConnectionError('connection refused')


def test_miss_stores_json_with_ttl(client, cache, seed_measurements):

    response = client.get('/measurements/latest')

    assert response.status_code == 200
    assert response.json()['id'] == 10
    assert '"id":10' in cache.store[newest_key(None)]
    assert cache.ttl[newest_key(None)] == TTL_SECONDS


def test_second_get_is_served_from_cache(client, db_session, seed_measurements):

    client.get('/measurements/latest')                                     # fills the cache
    db_session.execute(text("UPDATE measurements SET co2_ppm = 999 WHERE id = 10"))

    assert client.get('/measurements/10').json()['co2_ppm'] == 999        # DB has the new value
    assert client.get('/measurements/latest').json()['co2_ppm'] == 1490   # cache still the old one → proves the hit


def test_post_invalidates_only_affected_keys(client, cache, seed_measurements):

    client.get('/measurements/latest')
    client.get('/measurements/latest?device_id=esp-1')
    client.get('/measurements/latest?device_id=esp-2')

    new_id = client.post('/measurements', json=NEW_ESP1).json()['id']

    assert newest_key(None) not in cache.store
    assert newest_key('esp-1') not in cache.store
    assert newest_key('esp-2') in cache.store                              # other device untouched
    assert client.get('/measurements/latest').json()['id'] == new_id
    assert client.get('/measurements/latest?device_id=esp-1').json()['id'] == new_id


def test_delete_of_latest_invalidates(client, seed_measurements):

    client.get('/measurements/latest')

    assert client.delete('/measurements/10').status_code == 204
    assert client.get('/measurements/latest').json()['id'] == 9


def test_device_keys_are_separate(client, cache, seed_measurements):

    assert client.get('/measurements/latest').json()['id'] == 10
    assert client.get('/measurements/latest?device_id=esp-1').json()['id'] == 8
    assert set(cache.store) == {newest_key(None), newest_key('esp-1')}


def test_not_found_is_not_cached(client, cache, seed_measurements):

    assert client.get('/measurements/latest?device_id=esp-9').status_code == 404
    assert newest_key('esp-9') not in cache.store

    client.post('/measurements', json={**NEW_ESP1, 'device_id': 'esp-9'})

    assert client.get('/measurements/latest?device_id=esp-9').status_code == 200


def test_redis_down_falls_back_to_db(client, seed_measurements, caplog):

    main.app.dependency_overrides[cache_module.get_cache] = lambda: BrokenCache()

    assert client.get('/measurements/latest').json()['id'] == 10
    assert client.post('/measurements', json=NEW_ESP1).status_code == 201
    assert client.delete('/measurements/10').status_code == 204
    assert 'cache read failed' in caplog.text
    assert 'cache invalidation failed' in caplog.text
