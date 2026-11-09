"""Application services for road-segments."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from backend.dao.road_segment import RoadSegmentDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class RoadSegmentHandler:
    """Validate road-segments requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = RoadSegmentDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            ("name", "geom", "speed_limit_kph", "is_oneway", "direction"),
            ("name", "geom"),
            status=400,
            geometry_type="LineString",
        )
        return response(
            call_dao(self.dao.create_road_segment, error_status=400, **values), 201
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(
            query, ("name", "min_speed_kph", "max_speed_kph", "bbox")
        )
        items = call_dao(self.dao.list_road_segments, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_road_segments, **filters)
        return response(
            {
                "items": items,
                "limit": params["limit"],
                "offset": params["offset"],
                "count": count,
            }
        )

    def get(self, resource_id: str) -> JSONResponse:
        """Return one resource, or HTTP 404 when its ID does not exist."""
        return response(
            require_record(call_dao(self.dao.get_road_segment, path_id(resource_id)))
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            ("name", "geom", "speed_limit_kph", "is_oneway", "direction"),
            ("name", "geom"),
            update=True,
            status=400,
            geometry_type="LineString",
        )
        return response(
            require_record(
                call_dao(
                    self.dao.update_road_segment, identifier, error_status=400, **values
                )
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_road_segment, path_id(resource_id))
        )
        return response(
            {"message": "Road segment deleted successfully.", "road_id": identifier}
        )

    def geojson(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a paginated FeatureCollection with application/geo+json content type."""
        params = query_parameters(
            query,
            ("name", "min_speed_kph", "max_speed_kph"),
            status=422,
            default_limit=15000,
        )
        return response(
            call_dao(self.dao.get_road_segments_geojson, **params),
            media_type="application/geo+json",
        )
