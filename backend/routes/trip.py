"""Trip endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.trip import TripHandler

router = APIRouter(tags=["trips"])


@router.post("/trips", status_code=201)
def create_trip(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a trip from the specified resource fields."""
    return TripHandler().create(data)


@router.get("/trips")
def list_trips(request: Request) -> JSONResponse:
    """List trips with pagination and resource-specific filters."""
    return TripHandler().list(request.query_params)


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str) -> JSONResponse:
    """Get one trip by its positive integer ID."""
    return TripHandler().get(trip_id)


@router.put("/trips/{trip_id}")
def update_trip(trip_id: str, data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return TripHandler().update(trip_id, data)


@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: str) -> JSONResponse:
    """Delete one trip by its ID."""
    return TripHandler().delete(trip_id)


@router.get("/vehicles/{vehicle_id}/trips")
def vehicle_trips(vehicle_id: str, request: Request) -> JSONResponse:
    """List the vehicle's trips with pagination and time filters."""
    return TripHandler().for_vehicle(vehicle_id, request.query_params)
