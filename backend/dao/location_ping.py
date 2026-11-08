from psycopg.rows import dict_row

from backend.db import get_connection

from datetime import datetime

from psycopg.errors import ForeignKeyViolation

from psycopg.types.json import Jsonb

from psycopg import sql


_PING_TIME_FILTERS = sql.SQL(
    "(%(from_ts)s::timestamp IS NULL OR ts >= %(from_ts)s) "
    "AND (%(to_ts)s::timestamp IS NULL OR ts <= %(to_ts)s)"
)
_PING_FILTERS = sql.SQL(
    """
    (%(vehicle_id)s::bigint IS NULL OR vehicle_id = %(vehicle_id)s)
    AND {}
    AND (
        %(min_lon)s::double precision IS NULL
        OR ST_Intersects(
            geom,
            ST_MakeEnvelope(
                %(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326
            )
        )
    )
    """
).format(_PING_TIME_FILTERS)


def _list_filter_params(vehicle_id, from_ts, to_ts, bbox):
    min_lon, min_lat, max_lon, max_lat = bbox or (None, None, None, None)
    return {
        "vehicle_id": vehicle_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
    }


class InvalidPingVehicleError(ValueError):
    """The vehicle referenced by the ping does not exist."""

class LocationPingDAO:
    def get_location_ping(self, ping_id: int):
        """Return a location ping, or None if it does not exist."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT ping_id, vehicle_id, ts,
                       ST_AsGeoJSON(geom)::jsonb AS geom,
                       speed_kph, heading_deg
                FROM projectfall2026.location_ping
                WHERE ping_id = %s
                """,
                (ping_id,),
            )
            return cursor.fetchone()
    def list_location_pings(
        self,
        *,
        limit: int,
        offset: int,
        vehicle_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ):
        """Return a page of ping summaries matching the supplied filters."""
        params = _list_filter_params(vehicle_id, from_ts, to_ts, bbox)
        params.update(limit=limit, offset=offset)

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT ping_id, vehicle_id, ts, speed_kph, heading_deg
                    FROM projectfall2026.location_ping
                    WHERE {}
                    ORDER BY ping_id
                    LIMIT %(limit)s OFFSET %(offset)s
                    """
                ).format(_PING_FILTERS),
                params,
            )
            return cursor.fetchall()

    def count_location_pings(
        self,
        *,
        vehicle_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> int:
        """Count rows matching the list filters before pagination."""
        params = _list_filter_params(vehicle_id, from_ts, to_ts, bbox)
        query = sql.SQL(
            "SELECT count(*) FROM projectfall2026.location_ping WHERE {}"
        ).format(_PING_FILTERS)
        with get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def create_location_ping(
        self,
        *,
        vehicle_id: int,
        ts: datetime,
        geom: dict,
        speed_kph: float | None = None,
        heading_deg: float | None = None,
    ):
        """Insert a ping and return the saved row with its generated ID."""
        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO projectfall2026.location_ping
                        (vehicle_id, ts, geom, speed_kph, heading_deg)
                    VALUES (%s, %s, ST_GeomFromGeoJSON(%s), %s, %s)
                    RETURNING ping_id, vehicle_id, ts,
                              ST_AsGeoJSON(geom)::jsonb AS geom,
                              speed_kph, heading_deg
                    """,
                    (vehicle_id, ts, Jsonb(geom), speed_kph, heading_deg),
                )
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidPingVehicleError("Vehicle does not exist.") from exc
    def update_location_ping(self, ping_id: int, **changes):
        """Update the supplied fields and return the saved ping, or None."""
        allowed_fields = {"vehicle_id", "ts", "geom", "speed_kph", "heading_deg"}
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported ping field.")

        assignments = []
        values = []
        for field, value in changes.items():
            if field == "geom":
                assignments.append(sql.SQL("geom = ST_GeomFromGeoJSON(%s)"))
                values.append(Jsonb(value))
            else:
                assignments.append(sql.SQL("{} = %s").format(sql.Identifier(field)))
                values.append(value)

        query = sql.SQL(
            """
            UPDATE projectfall2026.location_ping
            SET {}
            WHERE ping_id = %s
            RETURNING ping_id, vehicle_id, ts,
                      ST_AsGeoJSON(geom)::jsonb AS geom,
                      speed_kph, heading_deg
            """
        ).format(sql.SQL(", ").join(assignments))

        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, (*values, ping_id))
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidPingVehicleError("Vehicle does not exist.") from exc
    def delete_location_ping(self, ping_id: int) -> int | None:
        """Delete a ping and return its ID, or None if it was missing."""
        with get_connection() as conn:
            deleted = conn.execute(
                """
                DELETE FROM projectfall2026.location_ping
                WHERE ping_id = %s
                RETURNING ping_id
                """,
                (ping_id,),
            ).fetchone()
            return None if deleted is None else deleted[0]
    def list_vehicle_pings(
        self,
        vehicle_id: int,
        *,
        limit: int,
        offset: int,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ):
        """Return a page of pings, or None if the vehicle is missing."""
        params = {
            "vehicle_id": vehicle_id,
            "limit": limit,
            "offset": offset,
            "from_ts": from_ts,
            "to_ts": to_ts,
        }

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT ping.ping_id, ping.ts,
                           ST_AsGeoJSON(ping.geom)::jsonb AS geom,
                           ping.speed_kph, ping.heading_deg
                    FROM projectfall2026.vehicle AS vehicle
                    LEFT JOIN LATERAL (
                        SELECT ping_id, ts, geom, speed_kph, heading_deg
                        FROM projectfall2026.location_ping
                        WHERE vehicle_id = vehicle.vehicle_id
                          AND {}
                        ORDER BY ping_id
                        LIMIT %(limit)s OFFSET %(offset)s
                    ) AS ping ON TRUE
                    WHERE vehicle.vehicle_id = %(vehicle_id)s
                    ORDER BY ping.ping_id
                    """
                ).format(_PING_TIME_FILTERS),
                params,
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            return [] if rows[0]["ping_id"] is None else rows

    def count_vehicle_pings(
        self,
        vehicle_id: int,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> int | None:
        """Count matching rows for a vehicle, or return None if it is missing."""
        query = sql.SQL(
            """
            SELECT (
                SELECT count(*)
                FROM projectfall2026.location_ping
                WHERE vehicle_id = vehicle.vehicle_id
                  AND {}
            )
            FROM projectfall2026.vehicle AS vehicle
            WHERE vehicle.vehicle_id = %(vehicle_id)s
            """
        ).format(_PING_TIME_FILTERS)
        params = {"vehicle_id": vehicle_id, "from_ts": from_ts, "to_ts": to_ts}
        with get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return None if row is None else row[0]
