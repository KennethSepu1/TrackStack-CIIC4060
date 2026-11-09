"""Road segment endpoints under /api/v1."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.handler.road_segment import RoadSegmentHandler

router = APIRouter(tags=["road-segments"])


@router.get("/road-segments/geojson", response_class=JSONResponse)
def road_geojson(request: Request) -> JSONResponse:
    """Return road features using name and speed filters, before the dynamic ID route."""
    return RoadSegmentHandler().geojson(request.query_params)


@router.post("/road-segments", status_code=201)
def create_road_segment(data: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Create a road segment from the specified resource fields."""
    return RoadSegmentHandler().create(data)


@router.get("/road-segments")
def list_road_segments(request: Request) -> JSONResponse:
    """List road-segments with pagination and resource-specific filters."""
    return RoadSegmentHandler().list(request.query_params)


@router.get("/road-segments/{road_id}")
def get_road_segment(road_id: str) -> JSONResponse:
    """Get one road segment by its positive integer ID."""
    return RoadSegmentHandler().get(road_id)


@router.put("/road-segments/{road_id}")
def update_road_segment(
    road_id: str, data: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    """Update any supported subset of the resource fields."""
    return RoadSegmentHandler().update(road_id, data)


@router.delete("/road-segments/{road_id}")
def delete_road_segment(road_id: str) -> JSONResponse:
    """Delete one road segment by its ID."""
    return RoadSegmentHandler().delete(road_id)
