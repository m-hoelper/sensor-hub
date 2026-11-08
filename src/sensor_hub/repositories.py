from sqlalchemy.orm import Session
from sqlalchemy import select, Row, func
from sensor_hub.models import Measurement
from datetime import datetime

class MeasurementRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, data: dict) -> Measurement:
        measurement = Measurement(**data)

        self.db.add(measurement)
        self.db.flush()

        return measurement

    def get(self, measurement_id: int) -> Measurement | None:
        stmt = select(Measurement)
        stmt = stmt.where(Measurement.id == measurement_id)

        return self.db.execute(stmt).scalar()

    def find(self, device_id: str | None, limit: int, offset: int) -> list[Measurement]:
        stmt = select(Measurement)

        if device_id is not None:
            stmt = stmt.where(Measurement.device_id == device_id)

        stmt = stmt.order_by(Measurement.created_at.desc(), Measurement.id.desc())
        stmt = stmt.limit(limit).offset(offset)

        return self.db.execute(stmt).scalars().all()

    def latest(self, device_id: str | None) -> Measurement | None:
        latest = self.find(device_id=device_id, limit=1, offset=0)

        if not latest:
            return None

        return latest[0]

    def delete(self, measurement_id: int) -> bool:
        measurement = self.get(measurement_id)

        if measurement is None:
            return False

        self.db.delete(measurement)
        self.db.flush()

        return True

    def get_co2_stats(self, device_id: str | None, start: datetime | None, end: datetime | None) -> Row:
        stmt = select(
            func.count().label('count'),
            func.avg(Measurement.co2_ppm).label('avg_co2'),
            func.max(Measurement.co2_ppm).label('max_co2'),
            func.min(Measurement.co2_ppm).label('min_co2'),
            )
        
        if start is not None:
            stmt = stmt.where(Measurement.created_at >= start)

        if end is not None:
            stmt = stmt.where(Measurement.created_at <= end)

        if device_id is not None:
            stmt = stmt.where(Measurement.device_id == device_id)

        return self.db.execute(stmt).one()