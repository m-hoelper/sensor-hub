from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

class Measurement(BaseModel):
    device_id: str
    co2_ppm: int
    temperature_c: float
    humidity_pct: float

MAX_LIMIT = 20
measurement_data: list[dict] = []
next_id = 1

app = FastAPI()

@app.post('/measurements', status_code=201)
def create_measurement(data: Measurement) -> dict:
    global next_id
    
    record = {
        **data.model_dump(),
        'id': next_id,
        'created_at': datetime.now(timezone.utc)
    }

    next_id += 1
    measurement_data.append(record)

    return record

@app.get('/measurements', status_code=200)
def get_measurements(device_id: str | None = None, limit: int = 10) -> list[dict]:

    temp_data = measurement_data

    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(400, f'limit:{limit} is invalid. must be greater than 0 and smaller equal {MAX_LIMIT}')

    if device_id is not None:
        temp_data = []
        for d in measurement_data:
            if d['device_id'] == device_id:
                temp_data.append(d)

    end = len(temp_data)

    if limit > end:
        limit = end

    data = temp_data[end - limit:]
    return data

@app.get('/measurements/latest')
def get_latest_measurement(device_id: str | None = None) -> dict:

    if not measurement_data:
        raise HTTPException(404, 'no data exist yet')

    if device_id is not None:
        for i in range(len(measurement_data) - 1, -1, -1):
            if measurement_data[i]['device_id'] == device_id:
                return measurement_data[i]
            
        raise HTTPException(404, f'no data for device: {device_id} exist yet')

    data = measurement_data[-1]
    return data

@app.get('/measurements/{measurement_id}', status_code=200)
def get_measurement_by_id(measurement_id: int) -> dict:

    if measurement_id <= 0:
        raise HTTPException(400, 'id is invalid. must be greater than 0')

    if measurement_id > len(measurement_data):
        raise HTTPException(404, 'data does not exist')

    data = measurement_data[measurement_id - 1]

    return data
