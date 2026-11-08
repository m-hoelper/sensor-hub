from fastapi import APIRouter, Depends, HTTPException, Path, Header, Query
from typing import Annotated
from sqlalchemy.orm import Session
from sensor_hub.db import get_db
from sensor_hub.schemas import MeasurementIn, MeasurementOut, StatsOut
import secrets
import sensor_hub.config as config
from sensor_hub.services import MeasurementService
from datetime import datetime

def verify_api_key(settings: Annotated[config.Settings, Depends(config.get_settings)], x_api_key: Annotated[str | None, Header()] = None) -> None:
    
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key.get_secret_value()):
        raise HTTPException(401, 'Authentification failed')

def get_service(db: Annotated[Session, Depends(get_db)]) -> MeasurementService:
    return MeasurementService(db)

router = APIRouter(prefix="/measurements", tags=["measurements"])

@router.post('', status_code=201, dependencies=[Depends(verify_api_key)])
def create_measurement(
    data: MeasurementIn,
    service: Annotated[MeasurementService, Depends(get_service)]) -> MeasurementOut:

    return service.create_measurement(data)

@router.get('', status_code=200)
def get_measurements(
    service: Annotated[MeasurementService, Depends(get_service)],
    device_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0)-> list[MeasurementOut]:

    return service.get_measurements(device_id, limit, offset)

@router.get('/latest', status_code=200)
def get_latest_measurement(
    service: Annotated[MeasurementService, Depends(get_service)],
    device_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None) -> MeasurementOut:

    measurement = service.get_latest_measurement(device_id)

    if measurement is None:
        raise HTTPException(404, 'data does not exist')

    return measurement

@router.get('/stats', status_code=200)
def get_co2_stats(
    service: Annotated[MeasurementService, Depends(get_service)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    device_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None) -> StatsOut:

        return service.get_co2_stats(device_id, start, end)

@router.delete('/{measurement_id}', status_code=204, dependencies=[Depends(verify_api_key)])
def delete_measurement(
    measurement_id: Annotated[int, Path(ge=1)],
    service: Annotated[MeasurementService, Depends(get_service)]) -> None:

    status = service.delete_measurement(measurement_id)

    if not status:
        raise HTTPException(404, 'data dose not exist')
    
    return None

@router.get("/{measurement_id}", status_code=200)
def get_measurement_by_id(
    measurement_id: Annotated[int, Path(ge=1)],
    service: Annotated[MeasurementService, Depends(get_service)]) -> MeasurementOut:

    measurement = service.get_measurement_by_id(measurement_id)

    if measurement is None:
        raise HTTPException(404, f"measurement: {measurement_id} not found")
    
    return measurement



