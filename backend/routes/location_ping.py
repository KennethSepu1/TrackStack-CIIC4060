"""Location ping endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.location_ping import LocationPingHandler

router = APIRouter(tags=["location-pings"])


@router.post("/location-pings", status_code=201)
def create_location_ping(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a location ping from the specified resource fields."""
    return LocationPingHandler().create(data)


@router.get("/location-pings")
def list_location_pings(request: Request) -> JSONResponse:
    """List location-pings with pagination and resource-specific filters."""
    return LocationPingHandler().list(request.query_params)


@router.get("/location-pings/{ping_id}")
def get_location_ping(ping_id: str) -> JSONResponse:
    """Get one location ping by its positive integer ID."""
    return LocationPingHandler().get(ping_id)


@router.put("/location-pings/{ping_id}")
def update_location_ping(
    ping_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return LocationPingHandler().update(ping_id, data)


@router.delete("/location-pings/{ping_id}")
def delete_location_ping(ping_id: str) -> JSONResponse:
    """Delete one location ping by its ID."""
    return LocationPingHandler().delete(ping_id)


@router.get("/vehicles/{vehicle_id}/pings")
def vehicle_pings(vehicle_id: str, request: Request) -> JSONResponse:
    """List the vehicle's pings with pagination and time filters."""
    return LocationPingHandler().for_vehicle(vehicle_id, request.query_params)
