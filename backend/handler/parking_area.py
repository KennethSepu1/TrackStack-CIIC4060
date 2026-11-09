"""Application services for parking-areas."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from backend.dao.parking_area import ParkingAreaDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class ParkingAreaHandler:
    """Validate parking-areas requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = ParkingAreaDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            ("name", "geom", "capacity"),
            ("name", "geom"),
            status=400,
            geometry_type="Polygon",
        )
        return response(
            call_dao(self.dao.create_parking_area, error_status=400, **values), 201
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(query, ("name", "bbox"))
        items = call_dao(self.dao.list_parking_areas, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_parking_areas, **filters)
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
            require_record(call_dao(self.dao.get_parking_area, path_id(resource_id)))
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            ("name", "geom", "capacity"),
            ("name", "geom"),
            update=True,
            status=400,
            geometry_type="Polygon",
        )
        return response(
            require_record(
                call_dao(
                    self.dao.update_parking_area, identifier, error_status=400, **values
                )
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_parking_area, path_id(resource_id))
        )
        return response(
            {
                "message": "Parking area deleted successfully.",
                "parking_area_id": identifier,
            }
        )
