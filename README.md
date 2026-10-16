# Car Tracking Phase I

Python ETL for CIIC 4060 / ICOM 5016. It reads the 11 official Parquet files and currently loads seven non-spatial tables into PostgreSQL 17. PostGIS loading and final database validation will be added in the next stage.

## Setup

Use Python 3.11 or later. Run these commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Inspect the dataset

```sh
python -m ETL inspect
```

The command prints each table's row count as JSON. It reports an error if a required file is missing or its columns differ from the project diagram. To use another dataset directory:

```sh
python -m ETL inspect --data-dir /path/to/dataset
```

`ETL/parquet.py` also provides `read_batches()` for reading files in batches of up to 10,000 rows. It keeps the original values and Arrow types, including NULLs, timestamps, and EWKB geometry strings.

## Load into PostgreSQL

Use Docker for testing, as required by the project:

```sh
docker compose -p ciic4060-stage2 up -d --wait
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m ETL load
```

The container uses PostgreSQL 17 with PostGIS available for the next stage. Its port is bound only to loopback. The image runs under `linux/amd64` emulation on Apple Silicon. `tests/schema.sql` creates the seven supported tables in a fresh container.

The load command inserts `fuel_type`, `vehicle_kind`, `vehicle_status`, `driver`, `vehicle_type`, `vehicle`, and `vehicle_assignment` in dependency order. All inserts share one transaction, so a failure rolls back the whole load. Repeating a load currently fails on existing primary keys. Timestamp conversion rejects values that cannot be stored exactly at PostgreSQL's microsecond precision.

Connection settings come from `DATABASE_URL`. The tables must already exist; the ETL does not create them. You can also pass `--schema` and `--batch-size`, for example:

```sh
python -m ETL load --schema public --batch-size 5000
```

This stage is a partial loader. `parking_area`, `road_segment`, `location_ping`, and `trip` are not loaded yet. Use the Docker test database while this work is in progress. Render remains the required database host for the final submission.

## Tests

```sh
python -m pytest -q
```

To include database integration tests, start Docker as shown above and set:

```sh
export TEST_DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m pytest -q
```

Without `TEST_DATABASE_URL`, database tests are skipped. They use separate schemas and only accept a loopback host with database name `ciic4060_test`. Tests cover stored values, foreign keys, rollback, duplicate keys, timestamp precision, and the command line. The official dataset is not modified.

Remove the test container and its data when finished:

```sh
docker compose -p ciic4060-stage2 down -v
```
