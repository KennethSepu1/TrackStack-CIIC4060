from psycopg.rows import dict_row
from psycopg import sql
from psycopg.errors import ForeignKeyViolation
from backend.db import get_connection

class DuplicatePlateError(ValueError):
    """The plate number is already registered."""


class InvalidVehicleReferenceError(ValueError):
    """The vehicle type or status does not exist."""

class VehicleInUseError(ValueError):
    """The vehicle is referenced by another record."""

class VehicleDAO:
    def get_vehicle(self, vehicle_id: int):
        """Return the vehicle record, or None if it doesn't exist."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT vehicle_id, vehicle_type_id, vehicle_status_id,
                       plate_number, make, model, year, created_at
                FROM projectfall2026.vehicle
                WHERE vehicle_id = %s
                """,
                (vehicle_id,),
            )
            return cursor.fetchone()

    def list_vehicles(
        self,
        *,
        limit: int,
        offset: int,
        plate_number: str | None = None,
        status: str | int | None = None,
    ):
        """Return a page of vehicles matching the supplied filters."""
        params = {
            "limit": limit,
            "offset": offset,
            "plate": plate_number,
            "status": None if status is None else str(status),
        }

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT v.vehicle_id, v.vehicle_type_id, v.vehicle_status_id,
                       v.plate_number, v.make, v.model, v.year, v.created_at
                FROM projectfall2026.vehicle AS v
                LEFT JOIN projectfall2026.vehicle_status AS s
                    ON s.vehicle_status_id = v.vehicle_status_id
                WHERE (
                    %(plate)s::text IS NULL
                    OR strpos(v.plate_number, %(plate)s) > 0
                )
                AND (
                    %(status)s::text IS NULL
                    OR s.name = %(status)s
                    OR v.vehicle_status_id::text = %(status)s
                )
                ORDER BY v.vehicle_id
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            return cursor.fetchall()

    def create_vehicle(
        self,
        *,
        vehicle_type_id: int,
        vehicle_status_id: int,
        plate_number: str,
        make: str | None = None,
        model: str | None = None,
        year: int | None = None,
    ):
        """Insert a vehicle and return the stored record."""
        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "LOCK TABLE projectfall2026.vehicle IN SHARE ROW EXCLUSIVE MODE"
                )
                cursor.execute(
                    "SELECT 1 FROM projectfall2026.vehicle WHERE plate_number = %s",
                    (plate_number,),
                )
                if cursor.fetchone() is not None:
                    raise DuplicatePlateError("Plate number already exists.")

                cursor.execute(
                    """
                    INSERT INTO projectfall2026.vehicle (
                        vehicle_type_id, vehicle_status_id, plate_number,
                        make, model, year, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s,
                            CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                    RETURNING vehicle_id, vehicle_type_id, vehicle_status_id,
                              plate_number, make, model, year, created_at
                    """,
                    (vehicle_type_id, vehicle_status_id, plate_number, make, model, year),
                )
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidVehicleReferenceError(
                "Vehicle type or status does not exist."
            ) from exc

    def update_vehicle(self, vehicle_id: int, **changes: int | str | None):
        """Update supplied fields and return the saved row, or None."""
        allowed_fields = {
            "vehicle_type_id", "vehicle_status_id", "plate_number",
            "make", "model", "year",
        }
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported vehicle field.")

        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(column))
            for column in changes
        )
        query = sql.SQL(
            """
            UPDATE projectfall2026.vehicle
            SET {}
            WHERE vehicle_id = %s
            RETURNING vehicle_id, vehicle_type_id, vehicle_status_id,
                      plate_number, make, model, year, created_at
            """
        ).format(assignments)
        changing_plate = "plate_number" in changes

        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                if changing_plate:
                    cursor.execute(
                        "LOCK TABLE projectfall2026.vehicle IN SHARE ROW EXCLUSIVE MODE"
                    )

                cursor.execute(query, (*changes.values(), vehicle_id))
                updated = cursor.fetchone()

                if changing_plate and updated is not None:
                    cursor.execute(
                        """
                        SELECT 1 FROM projectfall2026.vehicle
                        WHERE plate_number = %s AND vehicle_id <> %s
                        """,
                        (updated["plate_number"], vehicle_id),
                    )
                    if cursor.fetchone() is not None:
                        raise DuplicatePlateError("Plate number already exists.")

                return updated
        except ForeignKeyViolation as exc:
            raise InvalidVehicleReferenceError(
                "Vehicle type or status does not exist."
            ) from exc

    def delete_vehicle(self, vehicle_id: int) -> int | None:
        """Delete an unreferenced vehicle and return its ID, or None."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    """
                    DELETE FROM projectfall2026.vehicle
                    WHERE vehicle_id = %s
                    RETURNING vehicle_id
                    """,
                    (vehicle_id,),
                ).fetchone()
                return None if row is None else row[0]
        except ForeignKeyViolation as exc:
            raise VehicleInUseError(
                "Vehicle is referenced by another record."
            ) from exc

    def get_current_location(self, vehicle_id: int):
        """Return a vehicle with its latest ping, or None if it is missing."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT vehicle.vehicle_id, vehicle.plate_number,
                       status.name AS status, kind.name AS vehicle_kind,
                       fuel.name AS fuel_type, vehicle_type.emissions_rating,
                       ping.ts AS last_ts,
                       ST_AsGeoJSON(ping.geom)::jsonb AS last_geom,
                       ping.speed_kph, ping.heading_deg
                FROM projectfall2026.vehicle AS vehicle
                LEFT JOIN projectfall2026.vehicle_status AS status
                    ON status.vehicle_status_id = vehicle.vehicle_status_id
                LEFT JOIN projectfall2026.vehicle_type AS vehicle_type
                    ON vehicle_type.vehicle_type_id = vehicle.vehicle_type_id
                LEFT JOIN projectfall2026.vehicle_kind AS kind
                    ON kind.vehicle_kind_id = vehicle_type.vehicle_kind_id
                LEFT JOIN projectfall2026.fuel_type AS fuel
                    ON fuel.fuel_type_id = vehicle_type.fuel_type_id
                LEFT JOIN LATERAL (
                    SELECT ts, geom, speed_kph, heading_deg
                    FROM projectfall2026.location_ping
                    WHERE vehicle_id = vehicle.vehicle_id
                      AND ts IS NOT NULL
                    ORDER BY ts DESC, ping_id DESC
                    LIMIT 1
                ) AS ping ON TRUE
                WHERE vehicle.vehicle_id = %s
                """,
                (vehicle_id,),
            )
            return cursor.fetchone()
