"""FastAPI entry point: run with uvicorn backend.main:app."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError

from backend.routes import (
    driver,
    location_ping,
    parking_area,
    road_segment,
    trip,
    vehicle,
    vehicle_assignment,
)

app = FastAPI(title="Car Tracking API", version="2.0.0")
for routes in (
    vehicle,
    location_ping,
    trip,
    driver,
    vehicle_assignment,
    road_segment,
    parking_area,
):
    app.include_router(routes.router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def invalid_request(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Use 400 for malformed JSON and non-object request bodies."""
    return JSONResponse({"detail": "Expected a valid JSON object."}, status_code=400)


@app.exception_handler(DatabaseError)
async def database_error(request: Request, exc: DatabaseError) -> JSONResponse:
    """Keep database queries, connection details and credentials out of error responses."""
    return JSONResponse({"detail": "Database operation failed."}, status_code=500)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Report process readiness without exposing database configuration."""
    return {"status": "ok"}
