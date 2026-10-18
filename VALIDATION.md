# Validation

All results below come from commands run on 2026-10-16.

| Item | Result |
| ---- | ------ |
| Date | 2026-10-16 |
| Code commit tested | `52d828c` |
| Python | 3.12.15 in `.venv` |
| `pip check` | No broken requirements found |
| Docker database | PostgreSQL 17.5, PostGIS 3.5.2 |
| Render database | PostgreSQL 17.11, PostGIS 3.6.2 |

Dependencies were installed from `requirements-dev.txt` into a fresh `.venv`. Later commits change documentation only, so `ETL/`, `SQL/` and `tests/` are the same as in `52d828c`.

## Local and Docker

| Check | Result |
| ----- | ------ |
| `python -m ETL inspect` | 32,752 rows in 11 tables |
| `python -m pytest -q` without `TEST_DATABASE_URL` | 13 passed, 16 skipped |
| `python -m ETL load` on Docker, first run | Passed |
| `python -m ETL load` on Docker, second run | Passed, total still 32,752 rows |
| `python -m ETL validate` on Docker | Passed |
| `python -m pytest -q` with `TEST_DATABASE_URL` set to Docker | 29 passed, 0 skipped, 0 failed |

The Docker database was started with `docker compose -p ciic4060-stage2 up -d --wait`. Running the load twice did not duplicate any rows.

## Render

The Render checks did not change project records. `python -m ETL validate` used temporary tables to compare the Parquet data with the stored rows. The `psql` schema checks and SELECT queries ran with `default_transaction_read_only=on`. No load or mutation tests were run against Render during this validation.

| Check | Result |
| ----- | ------ |
| `python -m ETL validate` | Passed, 32,752 rows |
| `SQL/verify_schema.sql` tables | 11 of 11, PASS |
| `SQL/verify_schema.sql` columns and types | 54 of 54, PASS |
| `SQL/verify_schema.sql` primary keys | 11 of 11, PASS |
| `SQL/verify_schema.sql` foreign keys | 8 of 8, PASS |
| `SQL/verify_schema.sql` geometry and SRID | 5 of 5, PASS |

| Geometry column | Type | SRID | Dimensions |
| --------------- | ---- | ---: | ---------: |
| `location_ping.geom` | POINT | 4326 | 2 |
| `parking_area.geom` | POLYGON | 4326 | 2 |
| `road_segment.geom` | LINESTRING | 4326 | 2 |
| `trip.end_geom` | POINT | 4326 | 2 |
| `trip.start_geom` | POINT | 4326 | 2 |

## Diagram comparison

The official Moodle table diagram was compared with `SQL/schema.sql` and with the live Render schema. Table names, column names, data types, primary keys, foreign keys, geometry types and SRIDs match in both, with identical spelling.

| Object | Diagram | `SQL/schema.sql` | Render |
| ------ | ------: | ---------------: | -----: |
| Tables | 11 | 11 | 11 |
| Columns | 54 | 54 | 54 |
| Primary keys | 11 | 11 | 11 |
| Foreign keys | 8 | 8 | 8 |
| Geometry columns | 5 | 5 | 5 |

The diagram's `timestamp` is PostgreSQL's `timestamp without time zone`. Geometry type names were compared without regard to letter case.

## Row counts

| Table | Local `inspect` | Docker `validate` | Render `validate` |
| ----- | --------------: | ----------------: | ----------------: |
| fuel_type | 2 | 2 | 2 |
| vehicle_kind | 5 | 5 | 5 |
| vehicle_status | 2 | 2 | 2 |
| driver | 12 | 12 | 12 |
| vehicle_type | 8 | 8 | 8 |
| vehicle | 30 | 30 | 30 |
| parking_area | 224 | 224 | 224 |
| road_segment | 4,086 | 4,086 | 4,086 |
| vehicle_assignment | 42 | 42 | 42 |
| location_ping | 28,041 | 28,041 | 28,041 |
| trip | 300 | 300 | 300 |
| **Total** | **32,752** | **32,752** | **32,752** |
