from fastapi import FastAPI
import sensor_hub.routes.measurements as measurements
import sensor_hub.routes.settings as settings
import sensor_hub.routes.notifications as notifications
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI()

app.include_router(measurements.router)
app.include_router(settings.router)
app.include_router(notifications.router)
