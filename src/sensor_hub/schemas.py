from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime

class MeasurementIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=50)
    co2_ppm: int = Field(ge=0, le=40_000)
    temperature_c: float = Field(ge=-10, le=60)
    humidity_pct: float = Field(ge=0, le=100)

class MeasurementOut(MeasurementIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    count: int
    avg_co2: float | None = None
    max_co2: int | None = None
    min_co2: int | None = None

class ThresholdsIn(BaseModel):
    co2_open_ppm: int = Field(ge=0, le=40_000)
    co2_close_ppm: int = Field(ge=0, le=40_000)
    humidity_open_pct: float = Field(ge=0, le=100)
    humidity_close_pct: float = Field(ge=0, le=100)
    humidity_min_pct: float = Field(ge=0, le=100)
    cooldown_min: int = Field(ge=1)

    @model_validator(mode="after")
    def check_thresholds(self):
        if self.co2_close_ppm >= self.co2_open_ppm:
            raise ValueError('co2_close_ppm must be smaller than co2_open_ppm')
        if self.humidity_close_pct >= self.humidity_open_pct:
            raise ValueError('humidity_close_pct must be smaller than humidity_open_pct')
        if self.humidity_min_pct >= self.humidity_close_pct:
            raise ValueError('humidity_min_pct must be smaller than humidity_close_pct')
        return self

class ThresholdsPatch(BaseModel):
    co2_open_ppm: int | None = Field(ge=0, le=40_000, default=None)
    co2_close_ppm: int | None = Field(ge=0, le=40_000, default=None)
    humidity_open_pct: float | None = Field(ge=0, le=100, default=None)
    humidity_close_pct: float | None = Field(ge=0, le=100, default=None)
    humidity_min_pct: float | None = Field(ge=0, le=100, default=None)
    cooldown_min: int | None = Field(ge=1, default=None)

class ThresholdsOut(ThresholdsIn):
    model_config = ConfigDict(from_attributes=True)

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    measurement: MeasurementOut | None = None
    new_state: str
    message: str
    created_at: datetime
    sent_at: datetime | None = None
    attempts: int



