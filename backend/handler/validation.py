"""Strict request validation shared by the resource handlers."""

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from backend.dao._geometry import normalize_bbox, normalize_geometry

BIGINT_MAX = 2**63 - 1
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:[Zz]|[+-]\d{2}:\d{2})?"
)


def integer(value: Any, field: str, minimum: int = 0) -> int:
    """Require a JSON integer within the PostgreSQL bigint range."""
    if type(value) is not int or not minimum <= value <= BIGINT_MAX:
        raise ValueError(
            f"{field} must be an integer between {minimum} and {BIGINT_MAX}."
        )
    return value


def timestamp(value: Any) -> datetime:
    """Parse an ISO timestamp and normalize it to naive UTC for TIMESTAMP columns."""
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ValueError("Expected an RFC 3339 timestamp.")
    result = datetime.fromisoformat(value.upper())
    if result.tzinfo is not None:
        result = result.astimezone(UTC).replace(tzinfo=None)
    return result


def geometry(value: Any, expected: str) -> dict[str, Any]:
    """Validate WGS84 GeoJSON, rejecting alternate CRS and nonnumeric coordinates."""
    if not isinstance(value, dict) or "crs" in value:
        raise ValueError("Expected a GeoJSON geometry without a CRS member.")
    if expected != "Point":
        return normalize_geometry(value, expected)
    coords = value.get("coordinates")
    if (
        value.get("type") != "Point"
        or not isinstance(coords, list)
        or len(coords) != 2
        or any(type(n) not in (int, float) for n in coords)
        or not -180 <= coords[0] <= 180
        or not -90 <= coords[1] <= 90
    ):
        raise ValueError("Expected a WGS84 Point with [longitude, latitude].")
    return {"type": "Point", "coordinates": coords}


def path_id(value: str, status: int = 404) -> int:
    """Validate a positive bigint path ID using the endpoint's error status."""
    try:
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError
        return integer(int(value), "ID", 1)
    except ValueError:
        raise HTTPException(status, "Invalid resource ID.") from None


def query_parameters(
    query: Mapping[str, str],
    fields: tuple[str, ...],
    *,
    status: int = 400,
    default_limit: int = 20,
) -> dict[str, Any]:
    """Parse pagination and resource filters; reject reversed time and speed ranges."""
    result: dict[str, Any] = {}
    try:
        for name in ("limit", "offset", *fields):
            value = query.get(name)
            if value is None:
                if name in ("limit", "offset"):
                    result[name] = default_limit if name == "limit" else 0
                continue
            if name in (
                "limit",
                "offset",
                "vehicle_id",
                "driver_id",
                "min_speed_kph",
                "max_speed_kph",
            ):
                if not re.fullmatch(r"[0-9]+", value):
                    raise ValueError(f"{name} must be an integer.")
                result[name] = integer(
                    int(value), name, 1 if name.endswith("_id") else 0
                )
            elif name in ("from_ts", "to_ts"):
                result[name] = timestamp(value)
            elif name == "bbox":
                result[name] = normalize_bbox(tuple(float(n) for n in value.split(",")))
            elif name == "active":
                if value.lower() not in ("true", "false"):
                    raise ValueError("active must be true or false.")
                result[name] = value.lower() == "true"
            else:
                result[name] = value
    except (ValueError, OverflowError):
        raise HTTPException(status, "Invalid query parameters.") from None
    for low, high in (("from_ts", "to_ts"), ("min_speed_kph", "max_speed_kph")):
        if low in result and high in result and result[low] > result[high]:
            raise HTTPException(400, f"{low} cannot exceed {high}.")
    return result


def payload(
    data: dict[str, Any],
    fields: tuple[str, ...],
    required: tuple[str, ...],
    *,
    update: bool = False,
    status: int = 400,
    field_status: dict[str, int] | None = None,
    geometry_type: str = "Point",
) -> dict[str, Any]:
    """Validate supported fields, preserving explicit nulls and omitted update values."""
    unknown = data.keys() - set(fields)
    if unknown or not data:
        raise HTTPException(400, "Provide supported resource fields.")
    if not update and set(required) - data.keys():
        raise HTTPException(400, "Required fields are missing.")
    result = {}
    for name, value in data.items():
        code = (field_status or {}).get(name, status)
        try:
            if value is None:
                if name in required:
                    raise ValueError(f"{name} cannot be null.")
            elif name.endswith("_id"):
                value = integer(value, name, 1)
            elif name in ("year", "capacity", "speed_limit_kph"):
                value = integer(value, name)
                if name == "year" and not 1950 <= value <= 2100:
                    raise ValueError("year must be between 1950 and 2100.")
            elif name in ("speed_kph", "heading_deg", "distance_km"):
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError(f"{name} must be a finite nonnegative number.")
                if name == "heading_deg" and value >= 360:
                    raise ValueError("heading_deg must be less than 360.")
            elif name in (
                "ts",
                "start_ts",
                "end_ts",
                "hired_at",
                "assigned_from",
                "assigned_to",
            ):
                value = timestamp(value)
            elif name in ("geom", "start_geom", "end_geom"):
                value = geometry(value, geometry_type)
            elif name == "is_oneway":
                if type(value) is not bool:
                    raise ValueError("is_oneway must be a boolean.")
            else:
                if not isinstance(value, str) or "\x00" in value:
                    raise ValueError(f"{name} must be text without null bytes.")
                value = value.strip()
                if name in required and not value:
                    raise ValueError(f"{name} cannot be blank.")
                if name == "direction" and value not in ("both", "forward"):
                    raise ValueError("direction must be both or forward.")
            result[name] = value
        except (ValueError, OverflowError):
            raise HTTPException(code, f"Invalid {name}.") from None
    return result
