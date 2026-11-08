from datetime import datetime

from psycopg import sql
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import dict_row

from backend.db import get_connection


class DuplicateLicenseError(ValueError):
    """The license number is already assigned to a driver."""


class DriverInUseError(ValueError):
    """A vehicle assignment still references the driver."""


# The schema has no UNIQUE constraint on license_number.
_LICENSE_WRITE_LOCK = "LOCK TABLE projectfall2026.driver IN SHARE ROW EXCLUSIVE MODE"
_DRIVER_FILTERS = sql.SQL(
    """
    WHERE (
        %(name)s::text IS NULL
        OR strpos(lower(first_name), lower(%(name)s)) > 0
        OR strpos(lower(last_name), lower(%(name)s)) > 0
    )
      AND (
          %(license_number)s::text IS NULL
          OR strpos(lower(license_number), lower(%(license_number)s)) > 0
      )
    """
)


def _required_text(field: str, value) -> str:
    trimmed = value.strip() if isinstance(value, str) else ""
    if not trimmed:
        raise ValueError(f"{field} must be a nonempty string.")
    return trimmed


def _check_license_available(cursor, license_number: str, driver_id: int | None = None):
    cursor.execute(
        """
        SELECT 1
        FROM projectfall2026.driver
        WHERE btrim(license_number) = %(license_number)s
          AND (%(driver_id)s::bigint IS NULL OR driver_id <> %(driver_id)s)
        LIMIT 1
        """,
        {"license_number": license_number, "driver_id": driver_id},
    )
    if cursor.fetchone() is not None:
        raise DuplicateLicenseError("License number already exists.")


class DriverDAO:
    def get_driver(self, driver_id: int):
        """Return a driver, or None if it is missing."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT driver_id, first_name, last_name, license_number, hired_at
                FROM projectfall2026.driver
                WHERE driver_id = %s
                """,
                (driver_id,),
            )
            return cursor.fetchone()

    def list_drivers(
        self,
        *,
        limit: int,
        offset: int,
        name: str | None = None,
        license_number: str | None = None,
    ):
        """Return a page of drivers matching the supplied filters."""
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                        SELECT driver_id, first_name, last_name, license_number, hired_at
                        FROM projectfall2026.driver
                        {filters}
                        ORDER BY driver_id
                        LIMIT %(limit)s OFFSET %(offset)s
                    """
                ).format(filters=_DRIVER_FILTERS),
                {
                    "name": name,
                    "license_number": license_number,
                    "limit": limit,
                    "offset": offset,
                },
            )
            return cursor.fetchall()

    def count_drivers(
        self,
        *,
        name: str | None = None,
        license_number: str | None = None,
    ) -> int:
        """Count drivers matching the supplied filters before pagination."""
        with get_connection() as conn:
            return conn.execute(
                sql.SQL("SELECT count(*) FROM projectfall2026.driver {filters}").format(
                    filters=_DRIVER_FILTERS
                ),
                {"name": name, "license_number": license_number},
            ).fetchone()[0]

    def create_driver(
        self,
        *,
        first_name: str,
        last_name: str,
        license_number: str,
        hired_at: datetime,
    ):
        """Insert a driver and return the saved row with its generated ID."""
        first_name = _required_text("first_name", first_name)
        last_name = _required_text("last_name", last_name)
        license_number = _required_text("license_number", license_number)
        if not isinstance(hired_at, datetime) or hired_at.tzinfo is not None:
            raise ValueError("hired_at requires a UTC-normalized datetime.")

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(_LICENSE_WRITE_LOCK)
            _check_license_available(cursor, license_number)
            cursor.execute(
                """
                INSERT INTO projectfall2026.driver
                    (first_name, last_name, license_number, hired_at)
                VALUES (%s, %s, %s, %s)
                RETURNING driver_id, first_name, last_name, license_number, hired_at
                """,
                (first_name, last_name, license_number, hired_at),
            )
            return cursor.fetchone()

    def update_driver(self, driver_id: int, **changes: str | datetime | None):
        """Update the supplied fields and return the saved driver, or None."""
        allowed_fields = {"first_name", "last_name", "license_number", "hired_at"}
        if not changes or changes.keys() - allowed_fields:
            raise ValueError("Provide at least one supported driver field.")
        for field, value in changes.items():
            if field == "hired_at":
                if not isinstance(value, datetime) or value.tzinfo is not None:
                    raise ValueError("hired_at requires a UTC-normalized datetime.")
            else:
                changes[field] = _required_text(field, value)

        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(field)) for field in changes
        )
        query = sql.SQL(
            """
            UPDATE projectfall2026.driver
            SET {}
            WHERE driver_id = %s
            RETURNING driver_id, first_name, last_name, license_number, hired_at
            """
        ).format(assignments)

        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            if "license_number" in changes:
                cursor.execute(_LICENSE_WRITE_LOCK)
                cursor.execute(
                    "SELECT 1 FROM projectfall2026.driver WHERE driver_id = %s",
                    (driver_id,),
                )
                if cursor.fetchone() is None:
                    return None
                _check_license_available(cursor, changes["license_number"], driver_id)

            cursor.execute(query, (*changes.values(), driver_id))
            return cursor.fetchone()

    def delete_driver(self, driver_id: int) -> int | None:
        """Delete a driver and return its ID, or None if it was missing."""
        try:
            with get_connection() as conn:
                deleted = conn.execute(
                    """
                    DELETE FROM projectfall2026.driver
                    WHERE driver_id = %s
                    RETURNING driver_id
                    """,
                    (driver_id,),
                ).fetchone()
                return None if deleted is None else deleted[0]
        except ForeignKeyViolation as exc:
            raise DriverInUseError("Driver is referenced by a vehicle assignment.") from exc
