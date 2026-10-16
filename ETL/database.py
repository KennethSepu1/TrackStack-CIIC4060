"""Load the non-spatial tables into an existing PostgreSQL schema."""

from pathlib import Path

import pyarrow as pa
import psycopg
from psycopg import sql

from ETL.parquet import TABLE_COLUMNS, inspect_dataset, read_batches

# Parents must be inserted before the tables that reference them.
LOAD_TABLES = (
    "fuel_type", "vehicle_kind", "vehicle_status", "driver",
    "vehicle_type", "vehicle", "vehicle_assignment",
)


def load_data(connection: psycopg.Connection, directory: Path, *,
              schema: str = "public", batch_size: int = 10_000) -> dict[str, int]:
    """Insert seven tables in one transaction and return inserted row counts.

    Requires PostgreSQL 17, existing tables, and an idle connection with
    autocommit disabled. Existing primary keys cause an error. Any failure
    rolls back the entire load. The caller owns and closes the connection.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if connection.info.server_version // 10000 != 17:
        raise ValueError("PostgreSQL 17 is required")
    if connection.autocommit or connection.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("An idle connection with autocommit disabled is required")
    counts = inspect_dataset(directory)
    loaded: dict[str, int] = {}
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL timezone = 'UTC'")
            for table in LOAD_TABLES:
                columns = TABLE_COLUMNS[table]
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(schema, table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                loaded[table] = 0
                for batch in read_batches(directory / f"{table}.parquet", batch_size):
                    batch = batch.select(columns)
                    # PostgreSQL stores microseconds. Reject rounding and time
                    # zones rather than changing the source timestamps.
                    fields = []
                    for field in batch.schema:
                        if pa.types.is_timestamp(field.type):
                            if field.type.tz is not None:
                                raise ValueError(f"{table}.{field.name}: expected a timestamp without time zone")
                            field = field.with_type(pa.timestamp("us"))
                        fields.append(field)
                    batch = batch.cast(pa.schema(fields), safe=True)
                    records = zip(*(column.to_pylist() for column in batch.columns))
                    cursor.executemany(statement, records)
                    loaded[table] += batch.num_rows
                if loaded[table] != counts[table]:
                    raise ValueError(f"{table}: row count changed during reading")
    return loaded
