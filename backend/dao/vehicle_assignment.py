from datetime import datetime

from psycopg import sql
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import dict_row

from backend.db import get_connection


class InvalidAssignmentReferenceError(ValueError):
    """The vehicle or driver referenced by the assignment does not exist."""


class InvalidAssignmentTimeError(ValueError):
    """The assignment start or end time is invalid."""


def _validate_reference_id(field: str, value: int | None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")


def _validate_interval(
    assigned_from: datetime | None, assigned_to: datetime | None
) -> None:
    if not isinstance(assigned_from, datetime) or assigned_from.tzinfo is not None:
        raise InvalidAssignmentTimeError("assigned_from requires a UTC-normalized datetime.")
    if assigned_to is None:
        return
    if not isinstance(assigned_to, datetime) or assigned_to.tzinfo is not None:
        raise InvalidAssignmentTimeError("assigned_to requires a UTC-normalized datetime.")
    if assigned_to <= assigned_from:
        raise InvalidAssignmentTimeError("assigned_to must be after assigned_from.")


class VehicleAssignmentDAO:
    def get_vehicle_assignment(self, assignment_id: int):
        """Return one assignment, or None if it does not exist."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
                FROM projectfall2026.vehicle_assignment
                WHERE assignment_id = %s
                """,
                (assignment_id,),
            )
            return cursor.fetchone()

    def list_vehicle_assignments(
        self,
        *,
        limit: int,
        offset: int,
        vehicle_id: int | None = None,
        driver_id: int | None = None,
        active: bool | None = None,
    ):
        """Return assignment history matching all supplied filters."""
        if vehicle_id is not None:
            _validate_reference_id("vehicle_id", vehicle_id)
        if driver_id is not None:
            _validate_reference_id("driver_id", driver_id)
        params = {
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "active": active,
            "limit": limit,
            "offset": offset,
        }
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
                FROM projectfall2026.vehicle_assignment
                WHERE (%(vehicle_id)s::bigint IS NULL OR vehicle_id = %(vehicle_id)s)
                  AND (%(driver_id)s::bigint IS NULL OR driver_id = %(driver_id)s)
                  AND (%(active)s::boolean IS NULL OR (assigned_to IS NULL) = %(active)s)
                ORDER BY assignment_id
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            return cursor.fetchall()

    def create_vehicle_assignment(
        self,
        *,
        vehicle_id: int,
        driver_id: int,
        assigned_from: datetime,
        assigned_to: datetime | None = None,
    ):
        """Insert an assignment and return the saved record with its generated ID."""
        _validate_reference_id("vehicle_id", vehicle_id)
        _validate_reference_id("driver_id", driver_id)
        _validate_interval(assigned_from, assigned_to)
        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO projectfall2026.vehicle_assignment
                        (vehicle_id, driver_id, assigned_from, assigned_to)
                    VALUES (%s, %s, %s, %s)
                    RETURNING assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
                    """,
                    (vehicle_id, driver_id, assigned_from, assigned_to),
                )
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidAssignmentReferenceError("Vehicle or driver does not exist.") from exc

    def update_vehicle_assignment(
        self, assignment_id: int, **changes: int | datetime | None
    ):
        """Update supplied fields, preserving omitted values, or return None."""
        allowed_fields = {"vehicle_id", "driver_id", "assigned_from", "assigned_to"}
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported assignment field.")

        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(column)) for column in changes
        )
        query = sql.SQL(
            """
            UPDATE projectfall2026.vehicle_assignment
            SET {}
            WHERE assignment_id = %s
            RETURNING assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
            """
        ).format(assignments)

        try:
            with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT vehicle_id, driver_id, assigned_from, assigned_to
                    FROM projectfall2026.vehicle_assignment
                    WHERE assignment_id = %s
                    FOR UPDATE
                    """,
                    (assignment_id,),
                )
                stored = cursor.fetchone()
                if stored is None:
                    return None

                _validate_reference_id("vehicle_id", changes.get("vehicle_id", stored["vehicle_id"]))
                _validate_reference_id("driver_id", changes.get("driver_id", stored["driver_id"]))
                _validate_interval(
                    changes.get("assigned_from", stored["assigned_from"]),
                    changes.get("assigned_to", stored["assigned_to"]),
                )
                cursor.execute(query, (*changes.values(), assignment_id))
                return cursor.fetchone()
        except ForeignKeyViolation as exc:
            raise InvalidAssignmentReferenceError("Vehicle or driver does not exist.") from exc

    def delete_vehicle_assignment(self, assignment_id: int) -> int | None:
        """Delete an assignment and return its ID, or None if it was missing."""
        with get_connection() as conn:
            deleted = conn.execute(
                """
                DELETE FROM projectfall2026.vehicle_assignment
                WHERE assignment_id = %s
                RETURNING assignment_id
                """,
                (assignment_id,),
            ).fetchone()
            return None if deleted is None else deleted[0]
