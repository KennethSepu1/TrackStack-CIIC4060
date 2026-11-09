# Car Tracking Phase II

A FastAPI REST API over PostgreSQL 17 with PostGIS, hosted on Render. Requests go through routes, then handlers, then DAOs. All SQL is in `backend/dao`, and no ORM is used. Phase I loaded the 11 Car Tracking Parquet files into the database.

## Team

| Member            | Role                                       |
| ----------------- | ------------------------------------------ |
| Ian Ramos         | FastAPI routes and handlers                |
| Kenneth Sepulveda | DAOs, schema and Render deployment         |
| Wilson Morales    | Testing, validation and documentation      |

## Deployed API

| Item         | Value                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------ |
| Base URL     | <https://trackstack-api-lh8d.onrender.com>                                                 |
| Endpoints    | All 39 under `/api/v1`, for example `/api/v1/vehicles`                                     |
| Health check | `/health` returns `{"status":"ok"}`                                                        |
| API docs     | <https://trackstack-api-lh8d.onrender.com/docs>                                            |

The first request can take about a minute, because the Render free tier puts the service to sleep when it's idle.

The full endpoint contract is in [docs/phase2_endpoints.md](docs/phase2_endpoints.md). Trip time filters return trips that overlap the requested range. The default page size is 20, or 15000 for `/api/v1/road-segments/geojson`.

## Database access

| Setting  | Value                    |
| -------- | ------------------------ |
| Host     | `<HOST>`                 |
| Port     | `<PORT>`                 |
| Database | `<DATABASE>`             |
| User     | `<USER>`                 |
| Password | `<PASSWORD>`             |
| Schema   | `projectfall2026`        |
| SSL mode | `require`                |

PostgreSQL 17 with PostGIS. Geometry is stored in SRID 4326.

## Setup

Use Python 3.11 or later and run commands from the repository root.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Local database

All testing and data changes use Docker, never Render.

```sh
scripts/setup_test_db.sh
export DATABASE_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'
```

The script rebuilds the database from scratch on every run:

1. It starts PostgreSQL 17 and PostGIS 3.5 on port `55433`.
2. It loads the Phase I data.
3. It applies [SQL/phase2_schema_and_ids.sql](SQL/phase2_schema_and_ids.sql), which moves the tables to `projectfall2026` and adds generated IDs.

On Windows, run it from Git Bash or WSL. To remove it, run `docker compose -p ciic4060-stage2 down -v`.

Run the API locally:

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## API tests

`tests/api` sends HTTP requests to a running API.

| Variable        | Purpose                                                                                       |
| --------------- | --------------------------------------------------------------------------------------------- |
| `API_BASE_URL`  | API to test. Defaults to `http://127.0.0.1:8000`                                              |
| `ALLOW_WRITES`  | Set to `1` to run POST, PUT and DELETE tests. Local only: ignored for non-loopback URLs       |

Full run against the local API and Docker database:

```sh
ALLOW_WRITES=1 python -m pytest tests/api -q
```

Read-only run against the deployed API:

```sh
API_BASE_URL=https://trackstack-api-lh8d.onrender.com python -m pytest tests/api -q
```

The ETL and database tests run with `TEST_DATABASE_URL` set to the Docker URL above: `python -m pytest tests -q --ignore=tests/api`.

## Phase I loading and validation

```sh
python -m ETL inspect
python -m ETL load --data-dir phase1_official_dataset --schema public --batch-size 5000
python -m ETL validate --schema projectfall2026
```

`load` imports the tables in dependency order and converts EWKB geometry, requiring SRID 4326. It runs in one transaction and compares every stored value with the Parquet data, so any error rolls it back. `validate` checks existing data without inserting anything. Both read `DATABASE_URL`.

The Render data passed validation for all 11 tables and 32,752 records. The Phase II migration was applied to Render on November 7, 2026. See [VALIDATION.md](VALIDATION.md).

## Deployment

The root `Dockerfile` builds only `backend/` with `backend/requirements.txt`. [render.yaml](render.yaml) links the web service to the Render database through `DATABASE_URL`. The app runs no migrations or data loads at startup.
