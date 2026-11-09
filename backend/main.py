from fastapi import FastAPI

from backend.handler.common import register_error_handlers
from backend.routes import (
    drivers,
    location_pings,
    parking_areas,
    road_segments,
    trips,
    vehicle_assignments,
    vehicles,
)

API_PREFIX = "/api/v1"

app = FastAPI(title="TrackStack Car Tracking API")
register_error_handlers(app)

for module in (
    vehicles,
    drivers,
    vehicle_assignments,
    road_segments,
    parking_areas,
    location_pings,
    trips,
):
    app.include_router(module.router, prefix=API_PREFIX)
