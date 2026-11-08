from pydantic import BaseModel, Field, ConfigDict
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