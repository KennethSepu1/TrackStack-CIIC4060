"""Data access for road segments in the Phase II schema."""

from psycopg import sql
from psycopg.rows import dict_row

from backend.dao._geometry import (
    geometry_to_ewkb,
    list_parameters,
    normalize_bbox,
    normalize_name,
    normalize_nonnegative_bigint,
)
from backend.db import get_connection


_DETAIL_COLUMNS = sql.SQL(
    "road_id, name, speed_limit_kph, is_oneway, direction, "
    "ST_AsGeoJSON(geom)::jsonb AS geom, created_at"
)
_ROAD_FILTERS = sql.SQL(
    """
    (%(name)s::text IS NULL OR strpos(lower(name), lower(%(name)s::text)) > 0)
    AND (%(min_speed_kph)s::bigint IS NULL OR speed_limit_kph >= %(min_speed_kph)s)
    AND (%(max_speed_kph)s::bigint IS NULL OR speed_limit_kph <= %(max_speed_kph)s)
    """
)
_FEATURE_PROPERTIES = (
    "road_id", "name", "speed_limit_kph", "is_oneway", "direction", "created_at"
)


def _filter_params(limit, offset, name, min_speed_kph, max_speed_kph):
    params = list_parameters(limit, offset, name)
    minimum = normalize_nonnegative_bigint(min_speed_kph, "min_speed_kph")
    maximum = normalize_nonnegative_bigint(max_speed_kph, "max_speed_kph")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("min_speed_kph cannot exceed max_speed_kph.")
    return {
        **params,
        "min_speed_kph": minimum,
        "max_speed_kph": maximum,
    }


def _normalize_oneway(value: bool | None) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValueError("is_oneway must be a boolean.")
    return value


def _normalize_direction(value: str | None) -> str | None:
    if value is not None and value not in ("both", "forward"):
        raise ValueError("direction must be 'both' or 'forward'.")
    return value


class RoadSegmentDAO:
    def get_road_segment(self, road_id: int):
        """Return one road segment with its geometry, or None."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL("SELECT {} FROM projectfall2026.road_segment WHERE road_id = %s")
                .format(_DETAIL_COLUMNS),
                (road_id,),
            )
            return cursor.fetchone()

    def list_road_segments(
        self,
        *,
        limit: int,
        offset: int,
        name: str | None = None,
        min_speed_kph: int | None = None,
        max_speed_kph: int | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ):
        """Return a stable page of road summaries matching all supplied filters."""
        params = _filter_params(limit, offset, name, min_speed_kph, max_speed_kph)
        min_lon, min_lat, max_lon, max_lat = normalize_bbox(bbox)
        params.update(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)
        query = sql.SQL(
            """
            SELECT road_id, name, speed_limit_kph, created_at
            FROM projectfall2026.road_segment
            WHERE {}
              AND (
                  %(min_lon)s::double precision IS NULL
                  OR ST_Intersects(geom, ST_MakeEnvelope(
                      %(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326
                  ))
              )
            ORDER BY road_id
            LIMIT %(limit)s OFFSET %(offset)s
            """
        ).format(_ROAD_FILTERS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def create_road_segment(
        self,
        *,
        name: str,
        geom: dict,
        speed_limit_kph: int | None = None,
        is_oneway: bool | None = None,
        direction: str | None = None,
    ):
        """Insert a validated LineString and return the row with its generated ID."""
        name = normalize_name(name)
        speed_limit_kph = normalize_nonnegative_bigint(speed_limit_kph, "speed_limit_kph")
        is_oneway = _normalize_oneway(is_oneway)
        direction = _normalize_direction(direction)
        query = sql.SQL(
            """
            INSERT INTO projectfall2026.road_segment
                (name, speed_limit_kph, is_oneway, direction, geom, created_at)
            VALUES (%s, %s, %s, %s, ST_GeomFromEWKB(%s), CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            RETURNING {}
            """
        ).format(_DETAIL_COLUMNS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            ewkb = geometry_to_ewkb(conn, geom, "LineString")
            cursor.execute(query, (name, speed_limit_kph, is_oneway, direction, ewkb))
            return cursor.fetchone()

    def update_road_segment(self, road_id: int, **changes):
        """Update supplied fields only and return the saved row, or None."""
        allowed_fields = {"name", "speed_limit_kph", "is_oneway", "direction", "geom"}
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported road segment field.")
        if "name" in changes:
            changes["name"] = normalize_name(changes["name"])
        if "speed_limit_kph" in changes:
            changes["speed_limit_kph"] = normalize_nonnegative_bigint(
                changes["speed_limit_kph"], "speed_limit_kph"
            )
        if "is_oneway" in changes:
            changes["is_oneway"] = _normalize_oneway(changes["is_oneway"])
        if "direction" in changes:
            changes["direction"] = _normalize_direction(changes["direction"])

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            assignments = []
            values = []
            for field, value in changes.items():
                if field == "geom":
                    assignments.append(sql.SQL("geom = ST_GeomFromEWKB(%s)"))
                    values.append(geometry_to_ewkb(conn, value, "LineString"))
                else:
                    assignments.append(sql.SQL("{} = %s").format(sql.Identifier(field)))
                    values.append(value)
            query = sql.SQL(
                """
                UPDATE projectfall2026.road_segment
                SET {}
                WHERE road_id = %s
                RETURNING {}
                """
            ).format(sql.SQL(", ").join(assignments), _DETAIL_COLUMNS)
            cursor.execute(query, (*values, road_id))
            return cursor.fetchone()

    def delete_road_segment(self, road_id: int) -> int | None:
        """Delete a road segment and return its ID, or None if it was missing."""
        with get_connection() as conn:
            row = conn.execute(
                "DELETE FROM projectfall2026.road_segment WHERE road_id = %s RETURNING road_id",
                (road_id,),
            ).fetchone()
            return None if row is None else row[0]

    def get_road_segments_geojson(
        self,
        *,
        limit: int,
        offset: int,
        name: str | None = None,
        min_speed_kph: int | None = None,
        max_speed_kph: int | None = None,
    ):
        """Return a road FeatureCollection with a count before pagination."""
        params = _filter_params(limit, offset, name, min_speed_kph, max_speed_kph)
        query = sql.SQL(
            """
            WITH matching AS (
                SELECT road_id, name, speed_limit_kph, is_oneway, direction, geom, created_at
                FROM projectfall2026.road_segment
                WHERE {}
            )
            SELECT total.count, {}
            FROM (SELECT count(*) AS count FROM matching) AS total
            LEFT JOIN LATERAL (
                SELECT * FROM matching
                ORDER BY road_id
                LIMIT %(limit)s OFFSET %(offset)s
            ) AS page ON TRUE
            ORDER BY page.road_id
            """
        ).format(_ROAD_FILTERS, _DETAIL_COLUMNS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return {
            "type": "FeatureCollection",
            "count": rows[0]["count"],
            "limit": params["limit"],
            "offset": params["offset"],
            "features": [
                {
                    "type": "Feature",
                    "geometry": row["geom"],
                    "properties": {field: row[field] for field in _FEATURE_PROPERTIES},
                }
                for row in rows
                if row["road_id"] is not None
            ],
        }
