"""HTTP-safe serialization and DAO exception translation."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeVar

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.dao.driver import DriverInUseError, DuplicateLicenseError
from backend.dao.location_ping import InvalidPingVehicleError
from backend.dao.trip import InvalidTripTimeError, InvalidTripVehicleError
from backend.dao.vehicle import (
    DuplicatePlateError,
    InvalidVehicleReferenceError,
    VehicleInUseError,
)
from backend.dao.vehicle_assignment import (
    InvalidAssignmentReferenceError,
    InvalidAssignmentTimeError,
)

T = TypeVar("T")


def call_dao(
    operation: Callable[..., T], *args: Any, error_status: int = 400, **kwargs: Any
) -> T:
    """Map known domain errors to HTTP status codes without exposing database internals."""
    try:
        return operation(*args, **kwargs)
    except (
        DuplicatePlateError,
        VehicleInUseError,
        DuplicateLicenseError,
        DriverInUseError,
    ):
        raise HTTPException(
            409, "Resource conflicts with an existing record."
        ) from None
    except (
        InvalidVehicleReferenceError,
        InvalidPingVehicleError,
        InvalidTripVehicleError,
        InvalidAssignmentReferenceError,
    ):
        raise HTTPException(404, "Referenced resource does not exist.") from None
    except InvalidAssignmentTimeError:
        raise HTTPException(422, "Invalid assignment interval.") from None
    except InvalidTripTimeError:
        raise HTTPException(error_status, "Trip end must be after its start.") from None
    except ValueError:
        raise HTTPException(error_status, "Invalid resource values.") from None


def require_record(value: T | None) -> T:
    """Return an existing DAO result or raise a resource-specific 404."""
    if value is None:
        raise HTTPException(404, "Resource does not exist.")
    return value


def serialize(value: Any) -> Any:
    """Recursively serialize DAO rows, emitting UTC timestamps with a Z suffix."""
    if isinstance(value, datetime):
        value = (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    return value


def response(
    value: Any, status: int = 200, media_type: str = "application/json"
) -> JSONResponse:
    """Build a JSON response with normalized timestamps and the requested media type."""
    return JSONResponse(serialize(value), status_code=status, media_type=media_type)
