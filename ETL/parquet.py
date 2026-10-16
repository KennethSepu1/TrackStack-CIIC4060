"""Read Parquet files without changing their values or types."""

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


# File names and columns from the project table diagram.
TABLE_COLUMNS = {
    "fuel_type": ("fuel_type_id", "name"),
    "vehicle_kind": ("vehicle_kind_id", "name"),
    "vehicle_status": ("vehicle_status_id", "name"),
    "driver": ("driver_id", "first_name", "last_name", "license_number", "hired_at"),
    "vehicle_type": (
        "vehicle_type_id", "vehicle_kind_id", "fuel_type_id", "emissions_rating", "created_at",
    ),
    "vehicle": (
        "vehicle_id", "vehicle_type_id", "vehicle_status_id", "plate_number",
        "make", "model", "year", "created_at",
    ),
    "parking_area": ("parking_area_id", "name", "capacity", "geom", "created_at"),
    "road_segment": (
        "road_id", "name", "speed_limit_kph", "geom", "created_at", "is_oneway", "direction",
    ),
    "vehicle_assignment": (
        "assignment_id", "vehicle_id", "driver_id", "assigned_from", "assigned_to",
    ),
    "location_ping": ("ping_id", "vehicle_id", "ts", "geom", "speed_kph", "heading_deg"),
    "trip": (
        "trip_id", "vehicle_id", "start_ts", "end_ts", "start_geom", "end_geom", "distance_km",
    ),
}


def read_batches(path: Path, batch_size: int = 10_000) -> Iterator[pa.RecordBatch]:
    """Yield up to batch_size rows at a time, preserving Arrow types and NULLs.

    Raises ValueError for a nonpositive batch size. File and Parquet errors
    propagate to the caller.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    with pq.ParquetFile(path) as source:
        yield from source.iter_batches(batch_size=batch_size)


def inspect_dataset(directory: Path) -> dict[str, int]:
    """Check the eleven file schemas and return row counts from their metadata.

    Column order may vary. Missing, extra, or repeated column names raise
    ValueError. This does not check individual values or database types.
    """
    counts: dict[str, int] = {}
    for table, expected in TABLE_COLUMNS.items():
        with pq.ParquetFile(directory / f"{table}.parquet") as source:
            names = source.schema_arrow.names
            if len(names) != len(expected) or set(names) != set(expected):
                raise ValueError(f"{table}: columns do not match the project table diagram")
            counts[table] = source.metadata.num_rows
    return counts
