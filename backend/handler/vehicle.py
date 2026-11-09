"""Application services for vehicles."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse, Response

from backend.dao.vehicle import VehicleDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class VehicleHandler:
    """Validate vehicles requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = VehicleDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            (
                "vehicle_type_id",
                "vehicle_status_id",
                "plate_number",
                "make",
                "model",
                "year",
            ),
            ("vehicle_type_id", "vehicle_status_id", "plate_number"),
            status=400,
            geometry_type="Point",
        )
        return response(
            call_dao(self.dao.create_vehicle, error_status=400, **values), 201
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(query, ("status", "plate_number"))
        items = call_dao(self.dao.list_vehicles, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_vehicles, **filters)
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
            require_record(call_dao(self.dao.get_vehicle, path_id(resource_id)))
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            (
                "vehicle_type_id",
                "vehicle_status_id",
                "plate_number",
                "make",
                "model",
                "year",
            ),
            ("vehicle_type_id", "vehicle_status_id", "plate_number"),
            update=True,
            status=400,
            geometry_type="Point",
        )
        return response(
            require_record(
                call_dao(
                    self.dao.update_vehicle, identifier, error_status=400, **values
                )
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_vehicle, path_id(resource_id))
        )
        return response(
            {"message": "Vehicle deleted successfully.", "vehicle_id": identifier}
        )

    def current_location(self, vehicle_id: str) -> Response:
        """Return the newest ping, or an empty 204 for a vehicle without pings."""
        row = require_record(
            call_dao(self.dao.get_current_location, path_id(vehicle_id, 400))
        )
        if row["last_ts"] is None:
            return Response(status_code=204)
        return response(row)
