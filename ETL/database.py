"""Load and validate all eleven tables in PostgreSQL with PostGIS."""

from pathlib import Path

import pyarrow as pa
import psycopg
from psycopg import sql

from ETL.parquet import TABLE_COLUMNS, inspect_dataset, read_batches
from ETL.schema import COLUMN_TYPES, FOREIGN_KEYS, GEOMETRY_TYPES

# Parents must be inserted before the tables that reference them.
LOAD_TABLES = (
    "fuel_type", "vehicle_kind", "vehicle_status", "driver",
    "vehicle_type", "vehicle", "vehicle_assignment",
    "parking_area", "road_segment", "location_ping", "trip",
)


def check_schema(connection: psycopg.Connection, schema: str) -> None:
    """Require PostGIS and the diagram's column types, primary and foreign keys."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
        if not cursor.fetchone()[0]:
            raise ValueError("PostGIS must be enabled before loading")
        for table in LOAD_TABLES:
            types = {**COLUMN_TYPES, **GEOMETRY_TYPES.get(table, {})}
            expected = {name: types[name].lower() for name in TABLE_COLUMNS[table]}
            cursor.execute(
                """SELECT a.attname, lower(format_type(a.atttypid, a.atttypmod))
                   FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                   JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'
                   AND a.attnum > 0 AND NOT a.attisdropped""", (schema, table),
            )
            if dict(cursor.fetchall()) != expected:
                raise ValueError(f"{table}: columns or types differ from the project diagram")
            cursor.execute(
                """SELECT array_agg(a.attname ORDER BY k.ord)
                   FROM pg_constraint p JOIN pg_class c ON c.oid = p.conrelid
                   JOIN pg_namespace n ON n.oid = c.relnamespace
                   CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(num, ord)
                   JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.num
                   WHERE n.nspname = %s AND c.relname = %s AND p.contype = 'p'
                   GROUP BY p.oid""", (schema, table),
            )
            if cursor.fetchall() != [([TABLE_COLUMNS[table][0]],)]:
                raise ValueError(f"{table}: incorrect primary key")
        cursor.execute(
            """SELECT child.relname, ca.attname, parent.relname, pa.attname
               FROM pg_constraint f
               JOIN pg_class child ON child.oid = f.conrelid
               JOIN pg_namespace cn ON cn.oid = child.relnamespace
               JOIN pg_class parent ON parent.oid = f.confrelid
               JOIN pg_namespace pn ON pn.oid = parent.relnamespace
               JOIN pg_attribute ca ON ca.attrelid = child.oid AND ca.attnum = f.conkey[1]
               JOIN pg_attribute pa ON pa.attrelid = parent.oid AND pa.attnum = f.confkey[1]
               WHERE f.contype = 'f' AND cn.nspname = %s AND pn.nspname = %s
               AND cardinality(f.conkey) = 1 AND cardinality(f.confkey) = 1
               AND f.convalidated""", (schema, schema),
        )
        if set(FOREIGN_KEYS) - set(cursor.fetchall()):
            raise ValueError("Required foreign keys are missing or not validated")


def load_data(connection: psycopg.Connection, directory: Path, *,
              schema: str = "public", batch_size: int = 10_000,
              validate_only: bool = False) -> dict[str, int]:
    """Load and compare all values atomically, returning verified row counts.

    Requires PostgreSQL 17, existing tables, and an idle connection with
    autocommit disabled. Identical existing rows are accepted; differences
    cause rollback. validate_only compares without inserting destination rows.
    The caller owns and closes the connection.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if connection.info.server_version // 10000 != 17:
        raise ValueError("PostgreSQL 17 is required")
    if connection.autocommit or connection.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise ValueError("An idle connection with autocommit disabled is required")
    counts = inspect_dataset(directory)
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL timezone = 'UTC'")
            cursor.execute("SET LOCAL lock_timeout = '15s'")
            # Keep concurrent writes from changing the data during comparison.
            cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
                sql.SQL(", ").join(sql.Identifier(schema, table) for table in LOAD_TABLES)
            ))
            check_schema(connection, schema)
            for table in LOAD_TABLES:
                columns = TABLE_COLUMNS[table]
                names = sql.SQL(", ").join(map(sql.Identifier, columns))
                destination = sql.Identifier(schema, table)
                stage = sql.Identifier("pg_temp", "etl_stage")
                geometry = GEOMETRY_TYPES.get(table, {})
                definitions = sql.SQL(", ").join(
                    sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(
                        "text" if name in geometry else COLUMN_TYPES[name]
                    )) for name in columns
                )
                cursor.execute(sql.SQL("CREATE TEMP TABLE etl_stage ({}) ON COMMIT DROP").format(definitions))
                loaded = 0
                # COPY avoids one INSERT per row, especially for location_ping.
                with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(stage, names)) as copy:
                    for batch in read_batches(directory / f"{table}.parquet", batch_size):
                        batch = batch.select(columns)
                        fields = []
                        for field in batch.schema:
                            if pa.types.is_timestamp(field.type):
                                if field.type.tz is not None:
                                    raise ValueError(f"{table}.{field.name}: expected a timestamp without time zone")
                                field = field.with_type(pa.timestamp("us"))
                            fields.append(field)
                        # Reject any timestamp rounding to PostgreSQL precision.
                        batch = batch.cast(pa.schema(fields), safe=True)
                        for record in zip(*(column.to_pylist() for column in batch.columns)):
                            copy.write_row(record)
                        loaded += batch.num_rows
                if loaded != counts[table]:
                    raise ValueError(f"{table}: row count changed during reading")
                for name, dtype in geometry.items():
                    # A geometry without an SRID could otherwise acquire 4326
                    # implicitly when cast to the destination type.
                    cursor.execute(sql.SQL(
                        "SELECT EXISTS (SELECT 1 FROM {} WHERE {} IS NOT NULL "
                        "AND ST_SRID(ST_GeomFromEWKB(decode({}, 'hex'))) <> 4326)"
                    ).format(stage, sql.Identifier(name), sql.Identifier(name)))
                    if cursor.fetchone()[0]:
                        raise ValueError(f"{table}.{name}: source geometry must have SRID 4326")
                    cursor.execute(sql.SQL(
                        "ALTER TABLE {} ALTER COLUMN {} TYPE {} "
                        "USING ST_GeomFromEWKB(decode({}, 'hex'))"
                    ).format(stage, sql.Identifier(name), sql.SQL(dtype), sql.Identifier(name)))
                if not validate_only:
                    cursor.execute(sql.SQL(
                        "INSERT INTO {} ({}) SELECT {} FROM {} ON CONFLICT ({}) DO NOTHING"
                    ).format(destination, names, names, stage, sql.Identifier(columns[0])))
                # Compare both directions so extra rows and source duplicates fail.
                cursor.execute(sql.SQL(
                    "SELECT EXISTS (SELECT 1 FROM ((SELECT {} FROM {} EXCEPT ALL SELECT {} FROM {}) "
                    "UNION ALL (SELECT {} FROM {} EXCEPT ALL SELECT {} FROM {})) AS differences)"
                ).format(names, stage, names, destination, names, destination, names, stage))
                if cursor.fetchone()[0]:
                    raise ValueError(f"{table}: stored rows differ from Parquet")
                cursor.execute(sql.SQL("DROP TABLE {}").format(stage))
    return counts
