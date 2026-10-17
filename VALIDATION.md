# Validation

| Item | Result |
| ---- | ------ |
| Date | 2026-10-16 |
| Commit tested | `52d828c` |
| Python | 3.12.15 |
| `pip check` | No broken requirements found |
| `python -m pytest -q` | 13 passed, 16 skipped, 0 failed |
| `python -m ETL validate` on Render | Passed, 32,752 rows |

Dependencies were installed from `requirements-dev.txt` into a fresh `.venv`.

The 16 skipped tests are the database integration tests in `tests/test_database.py`. They skip because `TEST_DATABASE_URL` was not set, so the Docker database tests were not run.

The Render check was read only. `python -m ETL validate` was run once against the Render database with `DATABASE_URL` set for that command only. Validate mode compares the dataset to the existing tables through a temporary staging table and does not insert rows. No load and no tests were run against Render.

## Row counts

| Table | Local `inspect` | Render `validate` |
| ----- | --------------: | ----------------: |
| fuel_type | 2 | 2 |
| vehicle_kind | 5 | 5 |
| vehicle_status | 2 | 2 |
| driver | 12 | 12 |
| vehicle_type | 8 | 8 |
| vehicle | 30 | 30 |
| parking_area | 224 | 224 |
| road_segment | 4,086 | 4,086 |
| vehicle_assignment | 42 | 42 |
| location_ping | 28,041 | 28,041 |
| trip | 300 | 300 |
| **Total** | **32,752** | **32,752** |
