import pytest
from fastapi.testclient import TestClient
import sensor_hub.main as main
import sensor_hub.config as config

def get_test_settings() -> config.Settings:
    return config.Settings(api_key='test-key')

@pytest.fixture()
def client():
    main.app.dependency_overrides[config.get_settings] = get_test_settings

    yield TestClient(main.app, headers={'X-Api-Key': 'test-key'})
    
    main.app.dependency_overrides.clear()

@pytest.fixture()
def no_header_client():
    main.app.dependency_overrides[config.get_settings] = get_test_settings
    
    yield TestClient(main.app)

    main.app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def reset_states():
    main.measurement_data = {}
    main.next_id = 1

@pytest.fixture()
def seed_measurements(client, reset_states):
    SEED_MEASUREMENTS = [
    {"device_id": "esp-1", "co2_ppm": 420,  "temperature_c": 19.5, "humidity_pct": 35.0},
    {"device_id": "esp-2", "co2_ppm": 650,  "temperature_c": 21.0, "humidity_pct": 42.5},
    {"device_id": "esp-1", "co2_ppm": 780,  "temperature_c": 20.2, "humidity_pct": 38.0},
    {"device_id": "esp-3", "co2_ppm": 910,  "temperature_c": 23.4, "humidity_pct": 50.5},
    {"device_id": "esp-1", "co2_ppm": 1050, "temperature_c": 21.8, "humidity_pct": 44.0},
    {"device_id": "esp-2", "co2_ppm": 1180, "temperature_c": 24.1, "humidity_pct": 55.0},
    {"device_id": "esp-3", "co2_ppm": 1260, "temperature_c": 22.6, "humidity_pct": 61.5},
    {"device_id": "esp-1", "co2_ppm": 1340, "temperature_c": 25.0, "humidity_pct": 47.5},
    {"device_id": "esp-2", "co2_ppm": 1420, "temperature_c": 18.7, "humidity_pct": 32.0},
    {"device_id": "esp-3", "co2_ppm": 1490, "temperature_c": 25.9, "humidity_pct": 58.0},
    ]

    list_responses = []
    for payload in SEED_MEASUREMENTS:
        response = client.post('/measurements', json=payload)
        list_responses.append(response)

    return list_responses


