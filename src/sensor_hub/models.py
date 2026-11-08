from datetime import datetime, timezone
from sqlalchemy import String, func, Index, Identity, BIGINT, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sensor_hub.db import Base

class Measurement(Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    device_id: Mapped[str]
    co2_ppm: Mapped[int]
    temperature_c: Mapped[float]
    humidity_pct: Mapped[float]
    __table_args__ = (Index("ix_measurements_device_created", "device_id", "created_at"),)