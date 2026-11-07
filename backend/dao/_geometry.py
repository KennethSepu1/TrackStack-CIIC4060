from psycopg.types.json import Jsonb


def normalize_name(value: str) -> str:
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        raise ValueError("name must be a nonempty string.")
    return name


def normalize_nonnegative_bigint(value: int | None, field: str) -> int | None:
    if value is not None and (type(value) is not int or not 0 <= value < 2**63):
        raise ValueError(f"{field} must be a nonnegative integer.")
    return value


def list_parameters(limit: int, offset: int, name: str | None) -> dict:
    limit = normalize_nonnegative_bigint(limit, "limit")
    offset = normalize_nonnegative_bigint(offset, "offset")
    if limit is None or offset is None:
        raise ValueError("limit and offset are required.")
    if name is not None and not isinstance(name, str):
        raise ValueError("name filter must be text.")
    return {"limit": limit, "offset": offset, "name": name}


def _in_range(value, minimum: int, maximum: int) -> bool:
    return type(value) in (int, float) and minimum <= value <= maximum


def normalize_bbox(bbox):
    if bbox is None:
        return (None, None, None, None)
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("bbox must contain minLon, minLat, maxLon, maxLat.")

    min_lon, min_lat, max_lon, max_lat = bbox
    if not (
        _in_range(min_lon, -180, 180)
        and _in_range(max_lon, -180, 180)
        and _in_range(min_lat, -90, 90)
        and _in_range(max_lat, -90, 90)
        and min_lon < max_lon
        and min_lat < max_lat
    ):
        raise ValueError("bbox must use WGS84 coordinates with min < max.")
    return min_lon, min_lat, max_lon, max_lat


def _positions(value, minimum: int) -> list:
    if not isinstance(value, (list, tuple)) or len(value) < minimum:
        raise ValueError(f"Geometry requires at least {minimum} positions.")

    positions = []
    for position in value:
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
            or not _in_range(position[0], -180, 180)
            or not _in_range(position[1], -90, 90)
        ):
            raise ValueError("Geometry positions must be WGS84 longitude/latitude pairs.")
        positions.append(list(position))
    return positions


def normalize_geometry(geom: dict, expected_type: str) -> dict:
    if not isinstance(geom, dict) or geom.get("type") != expected_type:
        raise ValueError(f"geom must be a GeoJSON {expected_type}.")
    if geom.get("crs") is not None:
        raise ValueError("Use WGS84 coordinates without a custom GeoJSON CRS.")

    coordinates = geom.get("coordinates")
    if expected_type == "LineString":
        coordinates = _positions(coordinates, 2)
    elif expected_type == "Polygon":
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise ValueError("A Polygon must have at least one ring.")
        coordinates = [_positions(ring, 4) for ring in coordinates]
        if any(ring[0] != ring[-1] for ring in coordinates):
            raise ValueError("Polygon rings must be closed.")
    else:
        raise ValueError(f"Unsupported geometry type: {expected_type}.")

    return {"type": expected_type, "coordinates": coordinates}


def geometry_to_ewkb(connection, geom: dict, expected_type: str) -> bytes:
    """Validate geometry in PostGIS and return its SRID-tagged binary value."""
    normalized = normalize_geometry(geom, expected_type)
    valid, ewkb = connection.execute(
        """
        SELECT ST_IsValid(geom), ST_AsEWKB(geom)
        FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom) AS input
        """,
        (Jsonb(normalized),),
    ).fetchone()
    if not valid:
        raise ValueError(f"geom must be a valid {expected_type}.")
    return ewkb
