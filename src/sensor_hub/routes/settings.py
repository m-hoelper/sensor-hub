from fastapi import APIRouter, Depends, HTTPException
from sensor_hub.dependencies import verify_api_key, get_settings_service
from sensor_hub.schemas import ThresholdsOut, ThresholdsIn, ThresholdsPatch
from sensor_hub.services import SettingsService
from typing import Annotated
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get('/thresholds', status_code=200)
def get_thresholds(
    service: Annotated[SettingsService, Depends(get_settings_service)]) -> ThresholdsOut:

    return service.get()

@router.put('/thresholds', status_code=200, dependencies=[Depends(verify_api_key)])
def put_thresholds(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    thresholds: ThresholdsIn) -> ThresholdsOut:

    return service.replace(thresholds)

@router.patch('/thresholds', status_code=200, dependencies=[Depends(verify_api_key)])
def patch_thresholds(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    thresholds: ThresholdsPatch) -> ThresholdsOut:
    try:
        return service.patch(thresholds)

    except ValidationError as e:
        raise HTTPException(422, detail=jsonable_encoder(e.errors()))
