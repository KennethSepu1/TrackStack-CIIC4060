"""Driver endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.driver import DriverHandler

router = APIRouter(tags=["drivers"])


@router.post("/drivers", status_code=201)
def create_driver(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a driver from the specified resource fields."""
    return DriverHandler().create(data)


@router.get("/drivers")
def list_drivers(request: Request) -> JSONResponse:
    """List drivers with pagination and resource-specific filters."""
    return DriverHandler().list(request.query_params)


@router.get("/drivers/{driver_id}")
def get_driver(driver_id: str) -> JSONResponse:
    """Get one driver by its positive integer ID."""
    return DriverHandler().get(driver_id)


@router.put("/drivers/{driver_id}")
def update_driver(
    driver_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return DriverHandler().update(driver_id, data)


@router.delete("/drivers/{driver_id}")
def delete_driver(driver_id: str) -> JSONResponse:
    """Delete one driver by its ID."""
    return DriverHandler().delete(driver_id)
