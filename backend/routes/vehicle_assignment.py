"""Vehicle assignment endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.vehicle_assignment import VehicleAssignmentHandler

router = APIRouter(tags=["vehicle-assignments"])


@router.post("/vehicle-assignments", status_code=201)
def create_vehicle_assignment(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a vehicle assignment from the specified resource fields."""
    return VehicleAssignmentHandler().create(data)


@router.get("/vehicle-assignments")
def list_vehicle_assignments(request: Request) -> JSONResponse:
    """List vehicle-assignments with pagination and resource-specific filters."""
    return VehicleAssignmentHandler().list(request.query_params)


@router.get("/vehicle-assignments/{assignment_id}")
def get_vehicle_assignment(assignment_id: str) -> JSONResponse:
    """Get one vehicle assignment by its positive integer ID."""
    return VehicleAssignmentHandler().get(assignment_id)


@router.put("/vehicle-assignments/{assignment_id}")
def update_vehicle_assignment(
    assignment_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return VehicleAssignmentHandler().update(assignment_id, data)


@router.delete("/vehicle-assignments/{assignment_id}")
def delete_vehicle_assignment(assignment_id: str) -> JSONResponse:
    """Delete one vehicle assignment by its ID."""
    return VehicleAssignmentHandler().delete(assignment_id)
