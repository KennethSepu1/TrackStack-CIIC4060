"""Integration tests against the disposable Docker database."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
import pytest
from psycopg import sql

from ETL.database import LOAD_TABLES, load_data
from ETL.parquet import TABLE_COLUMNS, inspect_dataset
from ETL.schema import GEOMETRY_TYPES

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase1_official_dataset"


@pytest.fixture
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run Docker integration tests")
    options = psycopg.conninfo.conninfo_to_dict(url)
    if options.get("host") not in {"127.0.0.1", "localhost", "::1"} or options.get("dbname") != "ciic4060_test":
        pytest.fail("Tests require a loopback host and database ciic4060_test")
    schema = "etl_test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True, connect_timeout=15) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            schema_sql = (Path(__file__).parent / "schema.sql").read_text()
            admin.execute(schema_sql.replace("public.", f'"{schema}".'))
            with psycopg.connect(url, connect_timeout=15) as connection:
                yield connection, schema
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_load_preserves_all_values(database):
    connection, schema = database
    counts = inspect_dataset(DATA)
    assert load_data(connection, DATA, schema=schema, batch_size=257) == {
        table: counts[table] for table in LOAD_TABLES
    }
    with connection.transaction():
        for table in LOAD_TABLES:
            columns = TABLE_COLUMNS[table]
            geometry = GEOMETRY_TYPES.get(table, {})
            expressions = [
                sql.SQL("encode(ST_AsEWKB({}), 'hex')").format(sql.Identifier(name))
                if name in geometry else sql.Identifier(name) for name in columns
            ]
            actual = connection.execute(sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
                sql.SQL(", ").join(expressions),
                sql.Identifier(schema, table), sql.Identifier(columns[0]),
            )).fetchall()
            source = pq.read_table(DATA / f"{table}.parquet").select(columns)
            expected = [tuple(
                row[name].lower() if name in geometry and row[name] is not None else row[name]
                for name in columns
            ) for row in source.to_pylist()]
            assert actual == sorted(expected, key=lambda row: row[0])
    assert load_data(connection, DATA, schema=schema, validate_only=True) == counts


def test_foreign_key_failure_rolls_back_entire_load(database, tmp_path):
    connection, schema = database
    for path in DATA.glob("*.parquet"):
        shutil.copy2(path, tmp_path / path.name)
    path = tmp_path / "vehicle_assignment.parquet"
    source = pq.read_table(path)
    values = source["driver_id"].to_pylist()
    values[-1] = 999999
    source = source.set_column(source.schema.get_field_index("driver_id"), "driver_id", pa.array(values))
    pq.write_table(source, path)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        load_data(connection, tmp_path, schema=schema, batch_size=3)
    with connection.transaction():
        for table in LOAD_TABLES:
            assert connection.execute(sql.SQL("SELECT count(*) FROM {}").format(
                sql.Identifier(schema, table))).fetchone()[0] == 0


def test_repeat_load_keeps_existing_rows(database):
    connection, schema = database
    counts = load_data(connection, DATA, schema=schema)
    assert load_data(connection, DATA, schema=schema) == counts
    with connection.transaction():
        for table, expected in counts.items():
            assert connection.execute(sql.SQL("SELECT count(*) FROM {}").format(
                sql.Identifier(schema, table))).fetchone()[0] == expected


def test_reject_timestamp_rounding(database, tmp_path):
    connection, schema = database
    for path in DATA.glob("*.parquet"):
        shutil.copy2(path, tmp_path / path.name)
    path = tmp_path / "driver.parquet"
    source = pq.read_table(path)
    source = source.set_column(source.schema.get_field_index("hired_at"), "hired_at",
                               pa.array([1] * len(source), type=pa.timestamp("ns")))
    pq.write_table(source, path)
    with pytest.raises(pa.ArrowInvalid):
        load_data(connection, tmp_path, schema=schema)
    with connection.transaction():
        assert connection.execute(sql.SQL("SELECT count(*) FROM {}").format(
            sql.Identifier(schema, "fuel_type"))).fetchone()[0] == 0


def test_load_command(database):
    _, schema = database
    environment = os.environ.copy()
    environment["DATABASE_URL"] = environment["TEST_DATABASE_URL"]
    result = subprocess.run(
        [sys.executable, "-m", "ETL", "load", "--schema", schema, "--batch-size", "257"],
        cwd=ROOT, env=environment, text=True, capture_output=True, check=True,
    )
    assert set(json.loads(result.stdout)) == set(LOAD_TABLES)
    assert result.stderr == ""
    result = subprocess.run(
        [sys.executable, "-m", "ETL", "validate", "--schema", schema],
        cwd=ROOT, env=environment, text=True, capture_output=True, check=True,
    )
    assert json.loads(result.stdout) == inspect_dataset(DATA)


def test_load_command_requires_connection_settings(monkeypatch, capsys):
    from ETL.__main__ import main

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["ETL", "load"])
    assert main() == 1
    assert "Set DATABASE_URL before loading" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["srid", "missing_srid", "malformed", "duplicate"])
def test_late_geometry_or_duplicate_failure_rolls_back(database, tmp_path, failure):
    connection, schema = database
    for path in DATA.glob("*.parquet"):
        shutil.copy2(path, tmp_path / path.name)
    path = tmp_path / "trip.parquet"
    source = pq.read_table(path)
    if failure == "duplicate":
        source = pa.concat_tables([source, source.slice(0, 1)])
    else:
        values = source["start_geom"].to_pylist()
        if failure == "srid":
            values[-1] = values[-1].replace("E6100000", "110F0000", 1)
        elif failure == "missing_srid":
            values[-1] = "0101000000" + values[-1][18:]
        else:
            values[-1] = "invalid"
        source = source.set_column(source.schema.get_field_index("start_geom"), "start_geom", pa.array(values))
    pq.write_table(source, path)
    with pytest.raises((ValueError, psycopg.Error)):
        load_data(connection, tmp_path, schema=schema)
    with connection.transaction():
        for table in LOAD_TABLES:
            assert connection.execute(sql.SQL("SELECT count(*) FROM {}").format(
                sql.Identifier(schema, table))).fetchone()[0] == 0


@pytest.mark.parametrize("change", ["value", "geometry", "extra_row"])
def test_reject_destination_differences(database, change):
    connection, schema = database
    load_data(connection, DATA, schema=schema)
    with connection.transaction():
        if change == "value":
            connection.execute(sql.SQL("UPDATE {} SET first_name = 'Changed' WHERE driver_id = 1").format(
                sql.Identifier(schema, "driver")))
        elif change == "geometry":
            connection.execute(sql.SQL("UPDATE {} SET geom = ST_Translate(geom, 0.001, 0) WHERE ping_id = 1").format(
                sql.Identifier(schema, "location_ping")))
        else:
            connection.execute(sql.SQL("INSERT INTO {} (fuel_type_id, name) VALUES (999, 'Extra')").format(
                sql.Identifier(schema, "fuel_type")))
    for validate_only in (True, False):
        with pytest.raises(ValueError, match="stored rows differ"):
            load_data(connection, DATA, schema=schema, validate_only=validate_only)


def test_validate_empty_database_does_not_insert(database):
    connection, schema = database
    with pytest.raises(ValueError, match="stored rows differ"):
        load_data(connection, DATA, schema=schema, validate_only=True)
    with connection.transaction():
        assert connection.execute(sql.SQL("SELECT count(*) FROM {}").format(
            sql.Identifier(schema, "fuel_type"))).fetchone()[0] == 0


@pytest.mark.parametrize("change", ["type", "foreign_key", "primary_key"])
def test_reject_incorrect_schema(database, change):
    connection, schema = database
    with connection.transaction():
        if change == "type":
            connection.execute(sql.SQL("ALTER TABLE {} ALTER COLUMN geom TYPE geometry(Point,3857)").format(
                sql.Identifier(schema, "location_ping")))
        elif change == "foreign_key":
            connection.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT trip_vehicle_id_fkey").format(
                sql.Identifier(schema, "trip")))
        else:
            connection.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT trip_pkey").format(
                sql.Identifier(schema, "trip")))
    with pytest.raises(ValueError):
        load_data(connection, DATA, schema=schema)


def test_connection_error_does_not_print_secrets(monkeypatch, capsys):
    from ETL.__main__ import main

    def fail_connection(*args, **kwargs):
        raise psycopg.OperationalError("connection failed with private-password")

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private-password@localhost/test")
    monkeypatch.setattr(sys, "argv", ["ETL", "load"])
    monkeypatch.setattr(psycopg, "connect", fail_connection)
    assert main() == 1
    output = capsys.readouterr()
    assert "private-password" not in output.err + output.out
    assert "OperationalError" in output.err
