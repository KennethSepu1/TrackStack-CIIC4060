"""Parking area endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.parking_area import ParkingAreaHandler

router = APIRouter(tags=["parking-areas"])


@router.post("/parking-areas", status_code=201)
def create_parking_area(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a parking area from the specified resource fields."""
    return ParkingAreaHandler().create(data)


@router.get("/parking-areas")
def list_parking_areas(request: Request) -> JSONResponse:
    """List parking-areas with pagination and resource-specific filters."""
    return ParkingAreaHandler().list(request.query_params)


@router.get("/parking-areas/{parking_area_id}")
def get_parking_area(parking_area_id: str) -> JSONResponse:
    """Get one parking area by its positive integer ID."""
    return ParkingAreaHandler().get(parking_area_id)


@router.put("/parking-areas/{parking_area_id}")
def update_parking_area(
    parking_area_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return ParkingAreaHandler().update(parking_area_id, data)


@router.delete("/parking-areas/{parking_area_id}")
def delete_parking_area(parking_area_id: str) -> JSONResponse:
    """Delete one parking area by its ID."""
    return ParkingAreaHandler().delete(parking_area_id)
