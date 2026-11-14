from pydantic import BaseModel, Field, ConfigDict, model_validator, AwareDatetime
from datetime import datetime
from typing import Annotated

class MeasurementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    co2_ppm: Annotated[int, Field(ge=0, le=40_000)]
    temperature_c: Annotated[float, Field(ge=-10, le=60)]
    humidity_pct: Annotated[float, Field(ge=0, le=100)]
    created_at: AwareDatetime

class MeasurementOut(MeasurementItem):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: Annotated[str, Field(min_length=1, max_length=50)]

class MeasurementBatchIn(BaseModel):
    device_id: Annotated[str, Field(min_length=1, max_length=50)]
    measurements: Annotated[list[MeasurementItem], Field(min_length=1, max_length=500)]

class BatchResult(BaseModel):
    inserted: int
    duplicates: int
    
class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    count: int
    avg_co2: float | None = None
    max_co2: int | None = None
    min_co2: int | None = None

class ThresholdsIn(BaseModel):
    co2_open_ppm: Annotated[int, Field(ge=0, le=40_000)]
    co2_close_ppm: Annotated[int, Field(ge=0, le=40_000)]
    co2_max_ppm: Annotated[int, Field(ge=0, le=40_000)]
    humidity_open_pct: Annotated[float, Field(ge=0, le=100)]
    humidity_close_pct: Annotated[float, Field(ge=0, le=100)]
    humidity_min_pct: Annotated[float, Field(ge=0, le=100)]
    cooldown_min: Annotated[int, Field(ge=1)]
    ignore_measurements_older_than_min: Annotated[int, Field(ge=1, le=60)]

    @model_validator(mode="after")
    def check_thresholds(self):
        if self.co2_close_ppm >= self.co2_open_ppm:
            raise ValueError('co2_close_ppm must be smaller than co2_open_ppm')
        if self.co2_open_ppm >= self.co2_max_ppm:
            raise ValueError('co2_open_ppm must be smaller than co2_max_ppm')
        if self.humidity_close_pct >= self.humidity_open_pct:
            raise ValueError('humidity_close_pct must be smaller than humidity_open_pct')
        if self.humidity_min_pct >= self.humidity_close_pct:
            raise ValueError('humidity_min_pct must be smaller than humidity_close_pct')
        return self

class ThresholdsPatch(BaseModel):
    co2_open_ppm: Annotated[int | None, Field(ge=0, le=40_000)] = None
    co2_close_ppm: Annotated[int | None, Field(ge=0, le=40_000)] = None
    co2_max_ppm: Annotated[int | None, Field(ge=0, le=40_000)] = None
    humidity_open_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    humidity_close_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    humidity_min_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    cooldown_min: Annotated[int | None, Field(ge=1)] = None
    ignore_measurements_older_than_min: Annotated[int | None, Field(ge=1, le=60)] = None

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
