# Car Tracking Phase I

Loads the 11 Car Tracking Parquet files into PostgreSQL 17 with PostGIS. Uses Python and direct SQL.

## Team

| Member            | Role                                  |
| ----------------- | ------------------------------------- |
| Ian Ramos         | Python ETL                            |
| Kenneth Sepulveda | Schema and Render                     |
| Wilson Morales    | Testing, validation and documentation |

## Setup

Use Python 3.11 or later and run commands from the repository root.

Check `python3 --version` first. If it is older than 3.11, install a supported version and use that executable to create the environment, for example `python3.12 -m venv .venv`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ETL inspect
```

`inspect` checks the files and column names in `phase1_official_dataset/` and prints row counts.

## Test database

Build the local Docker database to match Render:

```sh
scripts/setup_test_db.sh
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m ETL validate --schema projectfall2026
```

The script removes any existing test container and volume, then:

1. starts PostgreSQL 17 and PostGIS 3.5 on local port `55433` with `compose.yaml`
2. loads the Phase I data into `public` with `python -m ETL load`
3. runs [SQL/phase2_schema_and_ids.sql](SQL/phase2_schema_and_ids.sql)
4. checks that the 11 tables are in `projectfall2026` and that the seven ID columns are identity columns, then runs [SQL/verify_phase2_ids.sql](SQL/verify_phase2_ids.sql), which rolls back its test rows

Rerunning the script rebuilds the database from scratch. It always connects to the Docker URL above, even when `DATABASE_URL` points somewhere else. It uses `.venv/bin/python` when that exists; set `PYTHON` to use another interpreter. Apple Silicon uses `linux/amd64` emulation.

## Loading and validation

`load` checks the schema and imports tables in dependency order. It converts EWKB geometry with `ST_GeomFromEWKB(decode(value, 'hex'))` and requires SRID 4326.

The import runs in one transaction and compares all stored values with the Parquet data. Repeating an identical load is safe. Errors or data differences roll back the import.

`validate` checks existing data without inserting destination records. Both commands require read, table-lock, and temporary-table permissions; `load` also requires insert permission.

NULLs and timestamp values are preserved. Timestamps that would lose precision are rejected.

Connection settings come from `DATABASE_URL`. The tables must already exist. Optional arguments:

```sh
python -m ETL load --data-dir phase1_official_dataset --schema public --batch-size 5000
```

## Tests

Start the Docker database above, then run:

```sh
export TEST_DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m pytest -q
```

Database tests are skipped when `TEST_DATABASE_URL` is unset. They use separate schemas in the local `ciic4060_test` database. Keep this variable pointed at Docker, not Render.

To remove the test container and its data:

```sh
docker compose -p ciic4060-stage2 down -v
```

## Render database

[SQL/schema.sql](SQL/schema.sql) enables PostGIS and creates the tables. [SQL/verify_schema.sql](SQL/verify_schema.sql) checks table definitions, keys, geometry types, and SRIDs using `psql`.

| Connection setting   | Value                                                     |
| -------------------- | --------------------------------------------------------- |
| PostgreSQL / PostGIS | 17.11 / 3.6.2                                             |
| Region               | Virginia (US East)                                        |
| External host        | `dpg-db8p4eks728c73aic0f0-a.virginia-postgres.render.com` |
| Port                 | `5432`                                                    |
| Database             | `car_tracking_o82k`                                       |
| User                 | `car_tracking_o82k_user`                                  |
| Password             | Shared separately by email                                |
| Schema               | `public`                                                  |
| SSL mode             | `require`                                                 |

Set `DATABASE_URL` to the external Render connection URL with `sslmode=require`, then run:

```sh
python -m ETL load
python -m ETL validate
```

The Render schema checks and data validation passed for all 11 tables and 32,752 records. See [VALIDATION.md](VALIDATION.md) for the full results.

## Phase II schema migration (Docker)

[scripts/setup_test_db.sh](scripts/setup_test_db.sh) applies the migration to
Docker as part of the [Test database](#test-database) setup. The migration moves
the 11 project tables to `projectfall2026` and adds generated IDs to seven API
tables while preserving explicit ETL IDs. It can only run once per database, so
the script rebuilds the database on every run.

On Windows, run `scripts/setup_test_db.sh` from Git Bash or WSL.

### Render verification

The Phase II migration was applied to Render on November 7, 2026. Read-only
checks confirmed 11 tables in `projectfall2026`, 32,752 rows, seven generated
ID columns, 11 primary keys, eight foreign keys, and five geometry columns
with SRID 4326.

Set `DATABASE_URL` in the backend environment to the Render PostgreSQL
connection string. Configure the Phase II backend to query `projectfall2026`.

## Phase II REST API

Start the API against the Docker test database:

```sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Routes use the `/api/v1` prefix and call handlers, which validate requests and
use the existing DAOs. Run `python -m pytest tests/unit -q` for offline tests.
Vehicle CRUD and current-location are available at `/api/v1/vehicles`.
