from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from datetime import datetime

class DataModel(BaseModel):
    device_id: str
    co2_ppm: int
    temperature_c: float
    humidity_pct: float


measurementData: list[dict] = []
idToIxd = {}
id = 1

app = FastAPI()

@app.post('/measurements', status_code=201)
def create(data: DataModel) -> dict:
    global id
    
    record = {
        **data.model_dump(),
        'id': id,
        'created_at': datetime.now()
    }

    id += 1
    measurementData.append(record)

    return record

@app.get('/measurements/getLatest')
def getLatest() -> dict:

    if not measurementData:
        raise HTTPException(404, 'no data exist yet')

    data = measurementData[-1]
    return data

@app.get('/measurements/items', status_code=200)
def get_measurement_items(device_id: str | None = None, limit: int = 10) -> list[dict]:

    tempData = measurementData

    MAX_LIMIT = 20
    if limit <= 0 or limit > MAX_LIMIT:
        raise HTTPException(400, f'limit:{limit} is invalid. must be greater than 0 and smaller equal {MAX_LIMIT}')

    if device_id is not None:
        tempData = []
        for d in measurementData:
            if d['device_id'] == device_id:
                tempData.append(d)

    end = len(tempData)

    if limit > end:
        limit = end

    data = tempData[end - limit:]
    return data

@app.get('/measurements/{measurement_id}', status_code=200)
def get_measurement_id(measurement_id: int) -> dict:

    if measurement_id <= 0:
        raise HTTPException(400, 'id is invalid. must be greater than 0')

    if measurement_id > len(measurementData):
        raise HTTPException(404, 'data does not exist')

    data = measurementData[measurement_id - 1]

    return data
