from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Annotated

class MeasurementIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=50)
    co2_ppm: int = Field(ge=0, le=40_000)
    temperature_c: float = Field(ge=-10, le=60)
    humidity_pct: float = Field(ge=0, le=100)

class MeasurementOut(MeasurementIn):
    id: int
    created_at: datetime

MAX_LIMIT = 20
measurement_data: dict[int, dict] = {}
next_id = 1

app = FastAPI()

@app.post('/measurements', status_code=201)
def create_measurement(data: MeasurementIn) -> MeasurementOut:
    global next_id
    
    record = {
        **data.model_dump(),
        'id': next_id,
        'created_at': datetime.now(timezone.utc)
    }

    measurement_data[next_id] = record
    next_id += 1

    return MeasurementOut(**record)

@app.get('/measurements', status_code=200)
def get_measurements(
    device_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0 )-> list[MeasurementOut]:

    keys = []
    
    for k in reversed(measurement_data.keys()):

        if device_id is not None:
            if measurement_data[k]['device_id'] == device_id:
                keys.append(k)
        else:
            keys.append(k)

        if len(keys) == limit + offset:
            break

    start = min(offset, len(keys))
    stop = min(offset + limit, len(keys))
    keys = keys[start:stop]

    return [MeasurementOut(**measurement_data[k]) for k in reversed(keys)]

@app.get('/measurements/latest')
def get_latest_measurement(device_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None) -> MeasurementOut:

    if not measurement_data:
        raise HTTPException(404, 'no data exist yet')


    for k in reversed(measurement_data.keys()):
        if device_id is not None:
            if measurement_data[k]['device_id'] == device_id:
                return MeasurementOut(**measurement_data[k])
        else:
            return MeasurementOut(**measurement_data[k])
            

    raise HTTPException(404, f'no data for device: {device_id} exist yet')

@app.get('/measurements/{measurement_id}', status_code=200)
def get_measurement_by_id(measurement_id: Annotated[int, Path(ge=1)]) -> MeasurementOut:

    if measurement_id not in measurement_data:
        raise HTTPException(404, 'data does not exist')

    return MeasurementOut(**measurement_data[measurement_id])

@app.delete('/measurements/{measurement_id}', status_code=204)
def delete_measurement(measurement_id: Annotated[int, Path(ge= 1)]) -> None:

    if measurement_id not in measurement_data:
        raise HTTPException(404, 'data dose not exist')

    del measurement_data[measurement_id]

    return
