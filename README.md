# Car Tracking Phase I

Loads the 11 Car Tracking Parquet files into PostgreSQL 17 with PostGIS. Uses Python and direct SQL.

## Setup

Use Python 3.11 or later and run commands from the repository root.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m ETL inspect
```

`inspect` checks the files and column names in `phase1_official_dataset/` and prints row counts.

## Test database

Start the Docker database and load the dataset:

```sh
docker compose -p ciic4060-stage2 up -d --wait
docker compose -p ciic4060-stage2 exec -T db psql -v ON_ERROR_STOP=1 -U etl_test -d ciic4060_test < tests/schema.sql
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
python -m ETL load
python -m ETL validate
```

The container runs PostgreSQL 17 and PostGIS 3.5 on local port `55433`. The SQL command creates any missing tables. Apple Silicon uses `linux/amd64` emulation.

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
| PostgreSQL / PostGIS | 17.11 / 3.6                                               |
| Region               | Virginia (US East)                                        |
| External host        | `dpg-db8p4eks728c73aic0f0-a.virginia-postgres.render.com` |
| Port                 | `5432`                                                    |
| Database             | `car_tracking_o82k`                                       |
| User                 | `car_tracking_o82k_user`                                  |
| Password             | Pending                                                   |
| Schema               | `public`                                                  |
| SSL mode             | `require`                                                 |

Set `DATABASE_URL` to the external Render connection URL with `sslmode=require`, then run:

```sh
python -m ETL load
python -m ETL validate
```

The Render schema checks and data validation passed for all 11 tables and 32,752 records.
