from typing import Annotated
from fastapi import Depends, Header, HTTPException
import secrets
import sensor_hub.config as config
from sqlalchemy.orm import Session
from sensor_hub.db import get_db
from sensor_hub.services import MeasurementService, NotificationService, SettingsService

def verify_api_key(
        settings: Annotated[config.Settings, Depends(config.get_settings)], 
        x_api_key: Annotated[str | None, Header()] = None) -> None:
    
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key.get_secret_value()):
        raise HTTPException(401, 'Authentification failed')

def get_measurement_service(db: Annotated[Session, Depends(get_db)]) -> MeasurementService:
    return MeasurementService(db)

def get_notification_service(db: Annotated[Session, Depends(get_db)]) -> NotificationService:
    return NotificationService(db)

def get_settings_service(db: Annotated[Session, Depends(get_db)]) -> SettingsService:
    return SettingsService(db)