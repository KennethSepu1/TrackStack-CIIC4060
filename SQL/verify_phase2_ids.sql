BEGIN;

DO $verify$
DECLARE
    resource record;
    old_max bigint;
    generated_id bigint;
    requested_id bigint;
    explicit_id bigint;
BEGIN
    IF current_database() <> 'ciic4060_test' THEN
        RAISE EXCEPTION 'Run this check only on the Docker test database.';
    END IF;

    FOR resource IN
        SELECT *
        FROM (VALUES
            ('vehicle', 'vehicle_id'),
            ('driver', 'driver_id'),
            ('vehicle_assignment', 'assignment_id'),
            ('road_segment', 'road_id'),
            ('parking_area', 'parking_area_id'),
            ('location_ping', 'ping_id'),
            ('trip', 'trip_id')
        ) AS resources(table_name, id_column)
    LOOP
        EXECUTE format(
            'SELECT COALESCE(MAX(%I), 0) FROM projectfall2026.%I',
            resource.id_column, resource.table_name
        ) INTO old_max;

        EXECUTE format(
            'INSERT INTO projectfall2026.%I DEFAULT VALUES RETURNING %I',
            resource.table_name, resource.id_column
        ) INTO generated_id;

        IF generated_id IS NULL OR generated_id <= old_max THEN
            RAISE EXCEPTION '%: generated ID must exceed %',
                resource.table_name, old_max;
        END IF;

        requested_id := generated_id + 1;
        EXECUTE format(
            'INSERT INTO projectfall2026.%I (%I) VALUES ($1) RETURNING %I',
            resource.table_name, resource.id_column, resource.id_column
        ) INTO explicit_id USING requested_id;

        IF explicit_id IS DISTINCT FROM requested_id THEN
            RAISE EXCEPTION '%: explicit ID was not preserved', resource.table_name;
        END IF;

        RAISE NOTICE 'PASS %: generated % (previous max %), accepted explicit %',
            resource.table_name, generated_id, old_max, explicit_id;
    END LOOP;
END;
$verify$;

ROLLBACK;