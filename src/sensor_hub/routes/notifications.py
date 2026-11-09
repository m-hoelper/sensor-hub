from fastapi import APIRouter, Depends, Query
from sensor_hub.dependencies import get_notification_service
from typing import Annotated
from sensor_hub.services import NotificationService
from sensor_hub.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get('')
def find_notifications(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    limit: Annotated[int, Query(ge=1, le=20,)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0) -> list[NotificationOut]:

    return service.find(limit, offset)