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


_DETAIL_FIELDS = sql.SQL(
    "parking_area_id, name, capacity, ST_AsGeoJSON(geom)::jsonb AS geom, created_at"
)


class ParkingAreaDAO:
    def get_parking_area(self, parking_area_id: int):
        """Return a parking area with its GeoJSON geometry, or None."""
        query = sql.SQL(
            "SELECT {} FROM projectfall2026.parking_area WHERE parking_area_id = %s"
        ).format(_DETAIL_FIELDS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, (parking_area_id,))
            return cursor.fetchone()

    def list_parking_areas(
        self,
        *,
        limit: int,
        offset: int,
        name: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ):
        """Return a page of summaries for parking areas that match the filters."""
        params = list_parameters(limit, offset, name)
        min_lon, min_lat, max_lon, max_lat = normalize_bbox(bbox)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT parking_area_id, name, capacity, created_at
                FROM projectfall2026.parking_area
                WHERE (
                    %(name)s::text IS NULL
                    OR strpos(lower(name), lower(%(name)s)) > 0
                )
                  AND (
                      %(min_lon)s::double precision IS NULL
                      OR ST_Intersects(
                          geom,
                          ST_MakeEnvelope(
                              %(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326
                          )
                      )
                  )
                ORDER BY parking_area_id
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    **params,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                },
            )
            return cursor.fetchall()

    def create_parking_area(self, *, name: str, geom: dict, capacity: int | None = None):
        """Insert a parking area and return it with its generated ID."""
        name = normalize_name(name)
        capacity = normalize_nonnegative_bigint(capacity, "capacity")
        query = sql.SQL(
            """
            INSERT INTO projectfall2026.parking_area (name, capacity, geom, created_at)
            VALUES (%s, %s, ST_GeomFromEWKB(%s), CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            RETURNING {}
            """
        ).format(_DETAIL_FIELDS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            ewkb = geometry_to_ewkb(conn, geom, "Polygon")
            cursor.execute(query, (name, capacity, ewkb))
            return cursor.fetchone()

    def update_parking_area(self, parking_area_id: int, **changes):
        """Update only the supplied fields and return the saved area, or None."""
        if not changes or changes.keys() - {"name", "capacity", "geom"}:
            raise ValueError("Provide at least one supported parking area field.")
        if "name" in changes:
            changes["name"] = normalize_name(changes["name"])
        if "capacity" in changes:
            changes["capacity"] = normalize_nonnegative_bigint(changes["capacity"], "capacity")

        assignments = sql.SQL(", ").join(
            sql.SQL("geom = ST_GeomFromEWKB(%s)")
            if field == "geom"
            else sql.SQL("{} = %s").format(sql.Identifier(field))
            for field in changes
        )
        query = sql.SQL(
            """
            UPDATE projectfall2026.parking_area
            SET {}
            WHERE parking_area_id = %s
            RETURNING {}
            """
        ).format(assignments, _DETAIL_FIELDS)
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            if "geom" in changes:
                changes["geom"] = geometry_to_ewkb(conn, changes["geom"], "Polygon")
            cursor.execute(query, (*changes.values(), parking_area_id))
            return cursor.fetchone()

    def delete_parking_area(self, parking_area_id: int) -> int | None:
        """Delete a parking area and return its ID, or None if it was missing."""
        with get_connection() as conn:
            deleted = conn.execute(
                """
                DELETE FROM projectfall2026.parking_area
                WHERE parking_area_id = %s
                RETURNING parking_area_id
                """,
                (parking_area_id,),
            ).fetchone()
            return None if deleted is None else deleted[0]
