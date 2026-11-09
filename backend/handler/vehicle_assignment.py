"""Application services for vehicle-assignments."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from backend.dao.vehicle_assignment import VehicleAssignmentDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class VehicleAssignmentHandler:
    """Validate vehicle-assignments requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = VehicleAssignmentDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            ("vehicle_id", "driver_id", "assigned_from", "assigned_to"),
            ("vehicle_id", "driver_id", "assigned_from"),
            status=400,
            geometry_type="Point",
            field_status={"assigned_from": 422, "assigned_to": 422},
        )
        return response(
            call_dao(self.dao.create_vehicle_assignment, error_status=400, **values),
            201,
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(query, ("vehicle_id", "driver_id", "active"))
        items = call_dao(self.dao.list_vehicle_assignments, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_vehicle_assignments, **filters)
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
            require_record(
                call_dao(self.dao.get_vehicle_assignment, path_id(resource_id))
            )
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            ("vehicle_id", "driver_id", "assigned_from", "assigned_to"),
            ("vehicle_id", "driver_id", "assigned_from"),
            update=True,
            status=400,
            geometry_type="Point",
            field_status={"assigned_from": 422, "assigned_to": 422},
        )
        return response(
            require_record(
                call_dao(
                    self.dao.update_vehicle_assignment,
                    identifier,
                    error_status=400,
                    **values,
                )
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_vehicle_assignment, path_id(resource_id))
        )
        return response(
            {
                "message": "Vehicle assignment deleted successfully.",
                "assignment_id": identifier,
            }
        )
