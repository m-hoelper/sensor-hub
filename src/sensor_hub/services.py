from sqlalchemy import Row
from sqlalchemy.orm import Session
from sensor_hub.repositories import MeasurementRepository, SettingsRepository, NotificationRepository
from sensor_hub.schemas import MeasurementIn, ThresholdsIn, ThresholdsPatch, ThresholdsOut
from sensor_hub.models import Measurement, ThresholdSettings, Notification
from datetime import datetime, timezone
from sensor_hub.rules import run_window_recommendation, build_message
import logging

logger = logging.getLogger(__name__)

class MeasurementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MeasurementRepository(db)
        self.settings_repo = SettingsRepository(db)
        self.notification_repo = NotificationRepository(db)

    def create_measurement(self, data: MeasurementIn) -> Measurement:

        measurement = self.repo.add(data.model_dump())

        settings = self.settings_repo.get()
        notification = self.notification_repo.latest()

        new_state = run_window_recommendation(data, settings, notification, datetime.now(timezone.utc))

        if new_state is not None:
            message = build_message(new_state, data, settings)
            self.notification_repo.add(new_state, message, measurement.id)

        self.db.commit()
        logger.info("created measurement id=%s device=%s co2=%s",
                    measurement.id, measurement.device_id, measurement.co2_ppm)
        return measurement

    def get_measurements(self, device_id: str | None, limit: int, offset: int) -> list[Measurement]:
        newest_first = self.repo.find(device_id, limit, offset)
        return newest_first

    def get_latest_measurement(self, device_id: str | None) -> Measurement | None:
        latest = self.repo.latest(device_id)
        return latest

    def delete_measurement(self, measurement_id: int) -> bool:
        status = self.repo.delete(measurement_id)
        self.db.commit()
        if status:
            logger.info("deleted measurement id=%s", measurement_id)
        else:
            logger.warning("delete failed: measurement id=%s not found", measurement_id)
        return status

    def get_measurement_by_id(self, measurement_id: int) -> Measurement | None:
        return self.repo.get(measurement_id)

    def get_co2_stats(self, device_id: str | None, start: datetime | None, end: datetime | None) -> Row:
        return self.repo.get_co2_stats(device_id, start, end)

class SettingsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SettingsRepository(db)

    def get(self) -> ThresholdSettings:
        return self.repo.get()

    def replace(self, data: ThresholdsIn) -> ThresholdSettings:
        settings = self.repo.update(data.model_dump())
        self.db.commit()
        logger.info("threshold settings updated: %s", data.model_dump())

        return settings

    def patch(self, patch: ThresholdsPatch) -> ThresholdSettings:
        current = ThresholdsOut.model_validate(self.get()).model_dump()
        changes = patch.model_dump(exclude_unset=True)
        current.update(changes)
        data = ThresholdsIn(**current)

        settings = self.replace(data)

        return settings

class NotificationService():
    def __init__(self, db: Session):
        self.db = db 
        self.repo = NotificationRepository(db)

    def find(self, limit: int, offset: int) -> list[Notification]:
        return self.repo.find(limit, offset)

