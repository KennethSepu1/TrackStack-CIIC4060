"""Application services for location-pings."""

from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from backend.dao.location_ping import LocationPingDAO
from backend.handler.responses import call_dao, require_record, response
from backend.handler.validation import path_id, payload, query_parameters


class LocationPingHandler:
    """Validate location-pings requests and delegate persistence to the DAO."""

    def __init__(self) -> None:
        self.dao = LocationPingDAO()

    def create(self, data: dict[str, Any]) -> JSONResponse:
        """Create a validated resource and return HTTP 201."""
        values = payload(
            data,
            ("vehicle_id", "ts", "geom", "speed_kph", "heading_deg"),
            ("vehicle_id", "ts", "geom"),
            status=400,
            geometry_type="Point",
            allow_naive=True,
        )
        return response(
            call_dao(self.dao.create_location_ping, error_status=400, **values), 201
        )

    def list(self, query: Mapping[str, str]) -> JSONResponse:
        """Return a filtered page with the total count before pagination."""
        params = query_parameters(
            query, ("vehicle_id", "from_ts", "to_ts", "bbox"), allow_naive=True
        )
        items = call_dao(self.dao.list_location_pings, **params)
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = call_dao(self.dao.count_location_pings, **filters)
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
            require_record(call_dao(self.dao.get_location_ping, path_id(resource_id)))
        )

    def update(self, resource_id: str, data: dict[str, Any]) -> JSONResponse:
        """Apply only supplied fields, preserving explicit nulls on optional fields."""
        identifier = path_id(resource_id)
        values = payload(
            data,
            ("vehicle_id", "ts", "geom", "speed_kph", "heading_deg"),
            ("vehicle_id", "ts", "geom"),
            update=True,
            status=400,
            geometry_type="Point",
            allow_naive=True,
        )
        return response(
            require_record(
                call_dao(
                    self.dao.update_location_ping,
                    identifier,
                    error_status=400,
                    **values,
                )
            )
        )

    def delete(self, resource_id: str) -> JSONResponse:
        """Delete a resource and return its ID; referenced resources remain intact."""
        identifier = require_record(
            call_dao(self.dao.delete_location_ping, path_id(resource_id))
        )
        return response(
            {"message": "Location ping deleted successfully.", "ping_id": identifier}
        )

    def for_vehicle(self, vehicle_id: str, query: Mapping[str, str]) -> JSONResponse:
        """Return a vehicle's filtered pings, distinguishing missing from empty."""
        identifier = path_id(vehicle_id)
        params = query_parameters(query, ("from_ts", "to_ts"), allow_naive=True)
        items = require_record(
            call_dao(self.dao.list_vehicle_pings, identifier, **params)
        )
        filters = {
            key: value
            for key, value in params.items()
            if key not in ("limit", "offset")
        }
        count = require_record(
            call_dao(self.dao.count_vehicle_pings, identifier, **filters)
        )
        return response(
            {
                "vehicle_id": identifier,
                "items": items,
                "limit": params["limit"],
                "offset": params["offset"],
                "count": count,
            }
        )
