from psycopg.rows import dict_row

from backend.db import get_connection

from datetime import datetime

from psycopg.errors import ForeignKeyViolation

from psycopg.types.json import Jsonb

from psycopg import sql


_TRIP_TIME_FILTERS = sql.SQL(
    "(%(from_ts)s::timestamp IS NULL OR end_ts >= %(from_ts)s) "
    "AND (%(to_ts)s::timestamp IS NULL OR start_ts <= %(to_ts)s)"
)
_TRIP_FILTERS = sql.SQL(
    """
    (%(vehicle_id)s::bigint IS NULL OR vehicle_id = %(vehicle_id)s)
    AND {}
    """
).format(_TRIP_TIME_FILTERS)


def _list_filter_params(vehicle_id, from_ts, to_ts):
    return {
        "vehicle_id": vehicle_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
    }


class InvalidTripVehicleError(ValueError):
    """The vehicle referenced by the trip does not exist."""


class InvalidTripTimeError(ValueError):
    """The trip end time must be after the start time."""

class TripDAO:
    def get_trip(self, trip_id: int):
        """Return a trip with both GeoJSON points, or None if it is missing."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT trip_id, vehicle_id, start_ts, end_ts,
                       ST_AsGeoJSON(start_geom)::jsonb AS start_geom,
                       ST_AsGeoJSON(end_geom)::jsonb AS end_geom,
                       distance_km
                FROM projectfall2026.trip
                WHERE trip_id = %s
                """,
                (trip_id,),
            )
            return cursor.fetchone()
    def list_trips(
        self,
        *,
        limit: int,
        offset: int,
        vehicle_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ):
        """Return trip summaries that overlap the supplied time window."""
        params = _list_filter_params(vehicle_id, from_ts, to_ts)
        params.update(limit=limit, offset=offset)

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT trip_id, vehicle_id, start_ts, end_ts, distance_km
                    FROM projectfall2026.trip
                    WHERE {}
                    ORDER BY trip_id
                    LIMIT %(limit)s OFFSET %(offset)s
                    """
                ).format(_TRIP_FILTERS),
                params,
            )
            return cursor.fetchall()

    def count_trips(
        self,
        *,
        vehicle_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> int:
        """Count rows matching the list filters before pagination."""
        params = _list_filter_params(vehicle_id, from_ts, to_ts)
        query = sql.SQL(
            "SELECT count(*) FROM projectfall2026.trip WHERE {}"
        ).format(_TRIP_FILTERS)
        with get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def create_trip(
        self,
        *,
        vehicle_id: int,
        start_ts: datetime,
        end_ts: datetime,
        start_geom: dict | None = None,
        end_geom: dict | None = None,
        distance_km: float | None = None,
    ):
        """Insert a trip and return the saved row with its generated ID."""
        if end_ts <= start_ts:
            raise InvalidTripTimeError("End time must be after start time.")
        if distance_km is not None and not distance_km >= 0:
            raise ValueError("Distance must be nonnegative.")

        start_point = Jsonb(start_geom) if start_geom is not None else None
        end_point = Jsonb(end_geom) if end_geom is not None else None

        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO projectfall2026.trip
                        (vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km)
                    VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s::jsonb),
                            ST_GeomFromGeoJSON(%s::jsonb), %s)
                    RETURNING trip_id, vehicle_id, start_ts, end_ts,
                              ST_AsGeoJSON(start_geom)::jsonb AS start_geom,
                              ST_AsGeoJSON(end_geom)::jsonb AS end_geom,
                              distance_km
                    """,
                    (vehicle_id, start_ts, end_ts, start_point, end_point, distance_km),
                )
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidTripVehicleError("Vehicle does not exist.") from exc
    def update_trip(self, trip_id: int, **changes):
        """Update the supplied fields and return the saved trip, or None."""
        allowed_fields = {
            "vehicle_id", "start_ts", "end_ts",
            "start_geom", "end_geom", "distance_km",
        }
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported trip field.")
        if "vehicle_id" in changes and changes["vehicle_id"] is None:
            raise ValueError("Vehicle ID is required.")

        distance_km = changes.get("distance_km")
        if distance_km is not None and not distance_km >= 0:
            raise ValueError("Distance must be nonnegative.")

        assignments = []
        values = []
        for field, value in changes.items():
            column = sql.Identifier(field)
            if field in {"start_geom", "end_geom"}:
                assignment = sql.SQL("{} = ST_GeomFromGeoJSON(%s::jsonb)")
                values.append(Jsonb(value) if value is not None else None)
            else:
                assignment = sql.SQL("{} = %s")
                values.append(value)
            assignments.append(assignment.format(column))

        query = sql.SQL(
            """
            UPDATE projectfall2026.trip
            SET {}
            WHERE trip_id = %s
            RETURNING trip_id, vehicle_id, start_ts, end_ts,
                      ST_AsGeoJSON(start_geom)::jsonb AS start_geom,
                      ST_AsGeoJSON(end_geom)::jsonb AS end_geom,
                      distance_km
            """
        ).format(sql.SQL(", ").join(assignments))

        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT start_ts, end_ts
                    FROM projectfall2026.trip
                    WHERE trip_id = %s
                    FOR UPDATE
                    """,
                    (trip_id,),
                )
                stored = cursor.fetchone()
                if stored is None:
                    return None

                start_ts = changes.get("start_ts", stored["start_ts"])
                end_ts = changes.get("end_ts", stored["end_ts"])
                if start_ts is None or end_ts is None or end_ts <= start_ts:
                    raise InvalidTripTimeError("End time must be after start time.")

                cursor.execute(query, (*values, trip_id))
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidTripVehicleError("Vehicle does not exist.") from exc
    def delete_trip(self, trip_id: int) -> int | None:
        """Delete a trip and return its ID, or None if it was missing."""
        with get_connection() as conn:
            deleted = conn.execute(
                """
                DELETE FROM projectfall2026.trip
                WHERE trip_id = %s
                RETURNING trip_id
                """,
                (trip_id,),
            ).fetchone()
            return None if deleted is None else deleted[0]
    def list_vehicle_trips(
        self,
        vehicle_id: int,
        *,
        limit: int,
        offset: int,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ):
        """Return a page of trips, or None if the vehicle is missing."""
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
                    SELECT trip.trip_id, trip.start_ts, trip.end_ts, trip.distance_km
                    FROM projectfall2026.vehicle AS vehicle
                    LEFT JOIN LATERAL (
                        SELECT trip_id, start_ts, end_ts, distance_km
                        FROM projectfall2026.trip
                        WHERE vehicle_id = vehicle.vehicle_id
                          AND {}
                        ORDER BY trip_id
                        LIMIT %(limit)s OFFSET %(offset)s
                    ) AS trip ON TRUE
                    WHERE vehicle.vehicle_id = %(vehicle_id)s
                    ORDER BY trip.trip_id
                    """
                ).format(_TRIP_TIME_FILTERS),
                params,
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            return [] if rows[0]["trip_id"] is None else rows

    def count_vehicle_trips(
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
                FROM projectfall2026.trip
                WHERE vehicle_id = vehicle.vehicle_id
                  AND {}
            )
            FROM projectfall2026.vehicle AS vehicle
            WHERE vehicle.vehicle_id = %(vehicle_id)s
            """
        ).format(_TRIP_TIME_FILTERS)
        params = {"vehicle_id": vehicle_id, "from_ts": from_ts, "to_ts": to_ts}
        with get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return None if row is None else row[0]
