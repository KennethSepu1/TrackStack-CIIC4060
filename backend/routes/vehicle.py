"""Vehicle endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from backend.handler.vehicle import VehicleHandler

router = APIRouter(tags=["vehicles"])


@router.post("/vehicles", status_code=201)
def create_vehicle(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a vehicle from the specified resource fields."""
    return VehicleHandler().create(data)


@router.get("/vehicles")
def list_vehicles(request: Request) -> JSONResponse:
    """List vehicles with pagination and resource-specific filters."""
    return VehicleHandler().list(request.query_params)


@router.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: str) -> JSONResponse:
    """Get one vehicle by its positive integer ID."""
    return VehicleHandler().get(vehicle_id)


@router.put("/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return VehicleHandler().update(vehicle_id, data)


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str) -> JSONResponse:
    """Delete one vehicle by its ID."""
    return VehicleHandler().delete(vehicle_id)


@router.get("/vehicles/{vehicle_id}/current-location")
def current_location(vehicle_id: str) -> Response:
    """Return the vehicle's latest location, or 204 when it has no pings."""
    return VehicleHandler().current_location(vehicle_id)
