#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT=ciic4060-stage2
DOCKER_URL='postgresql://etl_test:local_test_only@127.0.0.1:55433/ciic4060_test'

if [ -z "${PYTHON:-}" ]; then
    if [ -x .venv/bin/python ]; then
        PYTHON=.venv/bin/python
    elif [ -x .venv/Scripts/python.exe ]; then
        PYTHON=.venv/Scripts/python.exe
    else
        PYTHON=python3
    fi
fi

compose() {
    docker compose -p "$PROJECT" "$@"
}

psql_db() {
    compose exec -T -e PGPASSWORD=local_test_only db \
        psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U etl_test -d ciic4060_test "$@"
}

echo "==> Rebuilding the Docker database"
compose down -v --remove-orphans
compose up -d --wait

for attempt in $(seq 1 60); do
    ready=$(psql_db -tAc "SELECT to_regclass('public.trip') IS NOT NULL" 2>/dev/null || true)
    if [ "$ready" = "t" ]; then
        break
    fi
    if [ "$attempt" -eq 60 ]; then
        echo "The database did not finish initializing." >&2
        exit 1
    fi
    sleep 1
done

echo "==> Loading Phase I data into public"
DATABASE_URL="$DOCKER_URL" "$PYTHON" -m ETL load --schema public

echo "==> Applying SQL/phase2_schema_and_ids.sql"
psql_db -q -f - < SQL/phase2_schema_and_ids.sql

echo "==> Verifying projectfall2026"
psql_db -f - <<'SQL'
SELECT t.table_name,
       coalesce(c.column_name, '') AS identity_column,
       coalesce(c.identity_generation, '') AS generation,
       (xpath('/row/n/text()', query_to_xml(
           format('SELECT count(*) AS n FROM projectfall2026.%I', t.table_name),
           false, true, ''
       )))[1]::text::bigint AS row_count
FROM information_schema.tables AS t
LEFT JOIN information_schema.columns AS c
    ON c.table_schema = t.table_schema
   AND c.table_name = t.table_name
   AND c.is_identity = 'YES'
WHERE t.table_schema = 'projectfall2026'
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name;

DO $verify$
DECLARE
    table_count integer;
    missing text;
BEGIN
    SELECT count(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'projectfall2026'
      AND table_type = 'BASE TABLE'
      AND table_name IN (
          'fuel_type', 'vehicle_kind', 'vehicle_status', 'driver',
          'vehicle_type', 'vehicle', 'vehicle_assignment', 'parking_area',
          'road_segment', 'location_ping', 'trip'
      );
    IF table_count <> 11 THEN
        RAISE EXCEPTION 'Expected 11 tables in projectfall2026, found %.', table_count;
    END IF;

    SELECT string_agg(expected.table_name || '.' || expected.column_name, ', ')
    INTO missing
    FROM (VALUES
        ('vehicle', 'vehicle_id'),
        ('driver', 'driver_id'),
        ('vehicle_assignment', 'assignment_id'),
        ('road_segment', 'road_id'),
        ('parking_area', 'parking_area_id'),
        ('location_ping', 'ping_id'),
        ('trip', 'trip_id')
    ) AS expected(table_name, column_name)
    LEFT JOIN information_schema.columns AS c
        ON c.table_schema = 'projectfall2026'
       AND c.table_name = expected.table_name
       AND c.column_name = expected.column_name
       AND c.is_identity = 'YES'
    WHERE c.column_name IS NULL;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'ID columns are not identity: %.', missing;
    END IF;

    RAISE NOTICE 'PASS: 11 tables in projectfall2026, 7 identity ID columns.';
END;
$verify$;
SQL

psql_db -f - < SQL/verify_phase2_ids.sql

echo "==> Docker database ready"
echo "export DATABASE_URL='$DOCKER_URL'"
