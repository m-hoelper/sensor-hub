from sqlalchemy import Row
from sqlalchemy.orm import Session
from sensor_hub.repositories import MeasurementRepository
from sensor_hub.schemas import MeasurementIn
from sensor_hub.models import Measurement
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MeasurementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MeasurementRepository(db)

    def create_measurement(self, data: MeasurementIn) -> Measurement:
        measurement = self.repo.add(data.model_dump())
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