import pytest
from fastapi.testclient import TestClient
import sensor_hub.main as main
import sensor_hub.config as config
from sqlalchemy import create_engine
from sensor_hub.db import Base
from sqlalchemy.orm import Session
import sensor_hub.db as db
from sqlalchemy import text
from sensor_hub.repositories import NotificationRepository

def get_test_settings() -> config.Settings:
    return config.Settings(api_key='test-key')

@pytest.fixture(scope="session")
def engine():
    settings = get_test_settings()
    engine = create_engine(settings.test_database_url.get_secret_value())
    Base.metadata.create_all(engine)
    yield(engine)
    Base.metadata.drop_all(engine)

DEFAULT_THRESHOLDS = {
    "co2_open_ppm": 1200,
    "co2_close_ppm": 800,
    "humidity_open_pct": 65.0,
    "humidity_close_pct": 55.0,
    "humidity_min_pct": 30.0,
    "cooldown_min": 15,
}

@pytest.fixture()
def default_thresholds():
    return dict(DEFAULT_THRESHOLDS)

@pytest.fixture()
def db_session(engine):
    
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE measurements, threshold_settings, notifications RESTART IDENTITY"))
        conn.execute(text("INSERT INTO threshold_settings (co2_open_ppm, co2_close_ppm, humidity_open_pct, humidity_close_pct, humidity_min_pct, cooldown_min) "
                          "VALUES (:co2_open_ppm, :co2_close_ppm, :humidity_open_pct, :humidity_close_pct, :humidity_min_pct, :cooldown_min)"), DEFAULT_THRESHOLDS)

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    
    yield session

    session.close()
    transaction.rollback()        
    connection.close()


@pytest.fixture()
def client(db_session):

    def get_test_db():
        return db_session

    main.app.dependency_overrides[config.get_settings] = get_test_settings
    main.app.dependency_overrides[db.get_db] = get_test_db

    yield TestClient(main.app, headers={'X-Api-Key': 'test-key'})
    
    main.app.dependency_overrides.clear()

@pytest.fixture()
def no_header_client(db_session):

    def get_test_db():
        return db_session

    main.app.dependency_overrides[config.get_settings] = get_test_settings
    main.app.dependency_overrides[db.get_db] = get_test_db
    
    yield TestClient(main.app)

    main.app.dependency_overrides.clear()

@pytest.fixture()
def seed_measurements(client, db_session):
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
        list_responses.append(response.json())

    SEED_NOTIFICATIONS = [
    {"new_state": "CLOSED", "message": "CO2 420 ppm, humidity 35 %, close the window", "measurement_id": 1},
    {"new_state": "OPEN_RECOMMENDED", "message": "CO2 1260 ppm >= 1200, open the window", "measurement_id": 7},
    ]

    notification_repo = NotificationRepository(db_session)
    for notification in SEED_NOTIFICATIONS:
        notification_repo.add(**notification)

    return list_responses


