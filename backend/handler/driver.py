"""Application services for drivers."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from backend.dao.driver import DriverDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class DriverHandler:
    """Validate drivers requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = DriverDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            ("first_name", "last_name", "license_number", "hired_at"),
            ("first_name", "last_name", "license_number", "hired_at"),
            status=422,
            geometry_type="Point",
        )
        return response(
            call_dao(self.dao.create_driver, error_status=422, **values), 201
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(query, ("name", "license_number"))
        items = call_dao(self.dao.list_drivers, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_drivers, **filters)
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
            require_record(call_dao(self.dao.get_driver, path_id(resource_id)))
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            ("first_name", "last_name", "license_number", "hired_at"),
            ("first_name", "last_name", "license_number", "hired_at"),
            update=True,
            status=422,
            geometry_type="Point",
        )
        return response(
            require_record(
                call_dao(self.dao.update_driver, identifier, error_status=422, **values)
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_driver, path_id(resource_id))
        )
        return response(
            {"message": "Driver deleted successfully.", "driver_id": identifier}
        )
