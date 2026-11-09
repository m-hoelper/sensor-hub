from datetime import datetime
from sqlalchemy import func, Index, Identity, BIGINT, DateTime, CheckConstraint, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sensor_hub.db import Base

class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (Index("ix_measurements_device_created", "device_id", "created_at"),)
    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    device_id: Mapped[str]
    co2_ppm: Mapped[int]
    temperature_c: Mapped[float]
    humidity_pct: Mapped[float]

class ThresholdSettings(Base):
    __tablename__ = "threshold_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, server_default='1', autoincrement=False)
    co2_open_ppm: Mapped[int]
    co2_close_ppm: Mapped[int]
    humidity_open_pct: Mapped[float]
    humidity_close_pct: Mapped[float]
    humidity_min_pct: Mapped[float]
    cooldown_min: Mapped[int]

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index('ix_notifications_measurement_id', 'measurement_id'), Index("ix_notifications_unsent", "created_at", postgresql_where=text("sent_at IS NULL")),)
    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    measurement_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey('measurements.id', ondelete='SET NULL'))
    measurement: Mapped[Measurement | None] = relationship()
    new_state: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(server_default='0')
    last_error: Mapped[str | None]