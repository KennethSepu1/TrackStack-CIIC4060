import json
import math
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.dao._geometry import normalize_bbox

BIGINT_MAX = 2**63 - 1
DEFAULT_LIMIT = 20

_DIGITS = re.compile(r"[0-9]{1,19}")
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d{1,6})?([Zz]|[+-]\d{2}:\d{2})?"
)


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validation_status(status_code: int):
    def mark(endpoint):
        endpoint.validation_status = status_code
        return endpoint

    return mark


def _error(status_code: int, detail) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
    return _error(exc.status_code, exc.detail)


async def _request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    status_code = getattr(request.scope.get("endpoint"), "validation_status", 400)
    errors = [
        {"loc": list(error.get("loc", ())), "msg": error.get("msg", "")}
        for error in exc.errors()
    ]
    return _error(status_code, errors)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    return _error(500, "The service could not complete the request.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _request_validation_error)
    app.add_exception_handler(Exception, _unhandled_error)


@contextmanager
def dao_errors(mapping: dict[type[Exception], int]):
    try:
        yield
    except tuple(mapping) as exc:
        for error_type, status_code in mapping.items():
            if isinstance(exc, error_type):
                raise ApiError(status_code, str(exc)) from None
        raise


def _reject_constant(value):
    raise ValueError(f"{value} is not valid JSON.")


def parse_json_object(raw: bytes) -> dict:
    try:
        body = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise ApiError(400, "Request body must be valid JSON.") from None
    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return body


def is_integer(value) -> bool:
    return type(value) is int and -BIGINT_MAX - 1 <= value <= BIGINT_MAX


def is_positive_id(value) -> bool:
    return type(value) is int and 0 < value <= BIGINT_MAX


def is_number(value) -> bool:
    if type(value) is int:
        return abs(value) <= BIGINT_MAX
    return type(value) is float and math.isfinite(value)


def is_nonnegative_number(value) -> bool:
    return is_number(value) and value >= 0


def parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        return None
    text = value[:10] + "T" + value[11:]
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        return None
    return parsed


def format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat() + "Z"


def record(row: dict, fields: tuple[str, ...], timestamps: tuple[str, ...] = ()) -> dict:
    return {
        field: format_timestamp(row[field]) if field in timestamps else row[field]
        for field in fields
    }


def body_timestamp(value, field: str, status_code: int) -> datetime:
    parsed = parse_timestamp(value)
    if parsed is None:
        raise ApiError(status_code, f"{field} must be an RFC 3339 timestamp.")
    return parsed


def nonblank_text(value, field: str, status_code: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApiError(status_code, f"{field} must be a non-empty string.")
    return value.strip()


def optional_text(value, field: str, status_code: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(status_code, f"{field} must be a string.")
    return value.strip()


def require_fields(body: dict, fields: tuple[str, ...], status_code: int = 400) -> None:
    missing = [field for field in fields if field not in body]
    if missing:
        raise ApiError(status_code, f"Missing required fields: {', '.join(missing)}.")


def pick_fields(body: dict, fields: tuple[str, ...]) -> dict:
    return {field: body[field] for field in fields if field in body}


def update_fields(body: dict, fields: tuple[str, ...]) -> dict:
    changes = pick_fields(body, fields)
    if not changes:
        raise ApiError(400, f"Provide at least one of: {', '.join(fields)}.")
    return changes


def path_id(value: str) -> int | None:
    if _DIGITS.fullmatch(value) and 0 < int(value) <= BIGINT_MAX:
        return int(value)
    return None


def query_integer(
    value: str | None,
    field: str,
    *,
    minimum: int = 0,
    default: int | None = None,
    status_code: int = 400,
) -> int | None:
    if value is None:
        return default
    if not _DIGITS.fullmatch(value) or not minimum <= int(value) <= BIGINT_MAX:
        raise ApiError(status_code, f"{field} must be an integer greater than or equal to {minimum}.")
    return int(value)


def pagination(limit: str | None, offset: str | None, status_code: int = 400) -> tuple[int, int]:
    return (
        query_integer(limit, "limit", default=DEFAULT_LIMIT, status_code=status_code),
        query_integer(offset, "offset", default=0, status_code=status_code),
    )


def time_range(from_ts: str | None, to_ts: str | None) -> tuple[datetime | None, datetime | None]:
    start = None if from_ts is None else body_timestamp(from_ts, "from_ts", 400)
    end = None if to_ts is None else body_timestamp(to_ts, "to_ts", 400)
    if start is not None and end is not None and start > end:
        raise ApiError(400, "from_ts must not be later than to_ts.")
    return start, end


def query_boolean(value: str | None, field: str) -> bool | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered not in ("true", "false"):
        raise ApiError(400, f"{field} must be true or false.")
    return lowered == "true"


def query_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    parts = value.split(",")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        numbers = []
    if len(parts) != 4 or len(numbers) != 4 or not all(map(math.isfinite, numbers)):
        raise ApiError(400, "bbox must be four numbers: minLon,minLat,maxLon,maxLat.")
    try:
        return normalize_bbox(tuple(numbers))
    except ValueError:
        raise ApiError(400, "bbox must use WGS84 ranges with min values less than max values.") from None


def page(items: list, limit: int, offset: int, count: int, **extra) -> dict:
    return {**extra, "items": items, "limit": limit, "offset": offset, "count": count}


def _is_position(value) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(is_number(coordinate) for coordinate in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _coordinates(geom, geometry_type: str):
    if isinstance(geom, dict) and geom.get("type") == geometry_type and geom.get("crs") is None:
        return geom.get("coordinates")
    return None


def point(geom, field: str, status_code: int) -> dict:
    coordinates = _coordinates(geom, "Point")
    if not _is_position(coordinates):
        raise ApiError(status_code, f"{field} must be a GeoJSON Point with [longitude, latitude].")
    return {"type": "Point", "coordinates": list(coordinates)}


def line_string(geom, field: str, status_code: int) -> dict:
    coordinates = _coordinates(geom, "LineString")
    if not (
        isinstance(coordinates, list)
        and len(coordinates) >= 2
        and all(map(_is_position, coordinates))
    ):
        raise ApiError(status_code, f"{field} must be a GeoJSON LineString with at least two positions.")
    return {"type": "LineString", "coordinates": [list(position) for position in coordinates]}


def polygon(geom, field: str, status_code: int) -> dict:
    rings = _coordinates(geom, "Polygon")
    if not (
        isinstance(rings, list)
        and rings
        and all(
            isinstance(ring, list)
            and len(ring) >= 4
            and all(map(_is_position, ring))
            and ring[0] == ring[-1]
            for ring in rings
        )
    ):
        raise ApiError(status_code, f"{field} must be a closed GeoJSON Polygon.")
    return {
        "type": "Polygon",
        "coordinates": [[list(position) for position in ring] for ring in rings],
    }
