# Car Tracking Phase I

Python ETL for CIIC 4060 / ICOM 5016. It loads the 11 official Parquet files into PostgreSQL 17 with PostGIS, using direct SQL without an ORM.

## Setup

Use Python 3.11 or later. Run commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ETL inspect
```

`inspect` checks file and column names and prints row counts as JSON. `read_batches()` in `ETL/parquet.py` reads up to 10,000 rows at a time without changing the source values or Arrow types.

## Test database

Use Docker for testing, as required by the project:

```sh
docker compose -p ciic4060-stage2 up -d --wait
docker compose -p ciic4060-stage2 exec -T db psql -v ON_ERROR_STOP=1 -U etl_test -d ciic4060_test < tests/schema.sql
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m ETL load
python -m ETL validate
```

The SQL command also adds the spatial tables to an existing stage 2 test container. The container uses PostgreSQL 17 and PostGIS 3.5, with its port bound to loopback. The image uses `linux/amd64` emulation on Apple Silicon.

## Loading and validation

`load` checks the database column types, geometry types, SRIDs, primary keys, and foreign keys against the project diagram. It loads parent tables first and converts EWKB hex using `ST_GeomFromEWKB(decode(value, 'hex'))`. Source geometries must already have SRID 4326; they are not reprojected or repaired.

Data is copied in batches through temporary tables. All eleven tables share one transaction. After inserting, the ETL compares every column and row in both directions with `EXCEPT ALL`. Identical existing records are accepted. Different values, extra destination rows, duplicate source records, or other errors roll back the whole load.

`validate` performs the same checks without inserting destination records. Both commands block concurrent writes during comparison and wait up to 15 seconds for table locks. Use a database role with table ownership or the necessary insert, read, lock, and temporary-table permissions.

NULLs and original values are preserved. Timestamps remain without time zone; values that would lose precision at PostgreSQL's microsecond resolution are rejected.

Connection settings come from `DATABASE_URL`. The tables must already exist; the ETL does not create the production schema. Options include `--data-dir`, `--schema`, and `--batch-size`:

```sh
python -m ETL load --data-dir phase1_official_dataset --schema public --batch-size 5000
```

## Tests

Start the Docker database above, then run:

```sh
export TEST_DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m pytest -q
```

Without `TEST_DATABASE_URL`, database tests are skipped. Integration tests use separate schemas and only accept a loopback host with database name `ciic4060_test`. They check all stored values, geometry bytes, repeat loads, schema errors, rollback, timestamp precision, and command-line behavior. The official files are not modified.

To remove the test container and its data:

```sh
docker compose -p ciic4060-stage2 down -v
```

## Render submission

The final database must be hosted on Render. Kenneth must provide the production schema and external connection URL. Set `DATABASE_URL` with SSL enabled (`sslmode=require`), then run `load` and `validate`. The official dataset contains 32,752 records across 11 tables. Docker testing alone does not complete the submission.

The professor requires database credentials in the GitHub Classroom README. Before submission, add the actual host, port, database name, evaluation username, password, and SSL settings in the private team repository. Render credentials have not been supplied yet. Keep personal credentials and local `.env` files out of Git.
