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


def test_load_preserves_all_non_spatial_values(database):
    connection, schema = database
    counts = inspect_dataset(DATA)
    assert load_data(connection, DATA, schema=schema, batch_size=3) == {
        table: counts[table] for table in LOAD_TABLES
    }
    with connection.transaction():
        for table in LOAD_TABLES:
            columns = TABLE_COLUMNS[table]
            actual = connection.execute(sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.Identifier(schema, table), sql.Identifier(columns[0]),
            )).fetchall()
            source = pq.read_table(DATA / f"{table}.parquet").select(columns)
            expected = [tuple(row[name] for name in columns) for row in source.to_pylist()]
            assert actual == sorted(expected, key=lambda row: row[0])


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


def test_repeat_load_rejects_existing_keys(database):
    connection, schema = database
    counts = load_data(connection, DATA, schema=schema)
    with pytest.raises(psycopg.errors.UniqueViolation):
        load_data(connection, DATA, schema=schema)
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
        [sys.executable, "-m", "ETL", "load", "--schema", schema, "--batch-size", "3"],
        cwd=ROOT, env=environment, text=True, capture_output=True, check=True,
    )
    assert set(json.loads(result.stdout)) == set(LOAD_TABLES)
    assert result.stderr == ""


def test_load_command_requires_connection_settings(monkeypatch, capsys):
    from ETL.__main__ import main

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["ETL", "load"])
    assert main() == 1
    assert "Set DATABASE_URL before loading" in capsys.readouterr().err
