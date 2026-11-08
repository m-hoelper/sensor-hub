from fastapi import FastAPI
import sensor_hub.routes.measurements as measurements
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI()

app.include_router(measurements.router)
