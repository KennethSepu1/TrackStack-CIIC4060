-- Read-only schema verification against table diagram.png.
-- Run with psql after schema.sql. This script reads metadata only.
-- PASS means both the object count and the definitions match.
-- Column order and constraint names are not part of the comparison.
-- PostGIS extension tables, including spatial_ref_sys, are excluded.
\set ON_ERROR_STOP on
\pset pager off

\echo Schema verification
WITH
expected_columns (table_name, column_name, data_type) AS (
    VALUES
        ('fuel_type', 'fuel_type_id', 'bigint'),
        ('fuel_type', 'name', 'text'),
        ('vehicle_kind', 'vehicle_kind_id', 'bigint'),
        ('vehicle_kind', 'name', 'text'),
        ('vehicle_status', 'vehicle_status_id', 'bigint'),
        ('vehicle_status', 'name', 'text'),
        ('driver', 'driver_id', 'bigint'),
        ('driver', 'first_name', 'text'),
        ('driver', 'last_name', 'text'),
        ('driver', 'license_number', 'text'),
        ('driver', 'hired_at', 'timestamp without time zone'),
        ('vehicle_type', 'vehicle_type_id', 'bigint'),
        ('vehicle_type', 'vehicle_kind_id', 'bigint'),
        ('vehicle_type', 'fuel_type_id', 'bigint'),
        ('vehicle_type', 'emissions_rating', 'double precision'),
        ('vehicle_type', 'created_at', 'timestamp without time zone'),
        ('vehicle', 'vehicle_id', 'bigint'),
        ('vehicle', 'vehicle_type_id', 'bigint'),
        ('vehicle', 'vehicle_status_id', 'bigint'),
        ('vehicle', 'plate_number', 'text'),
        ('vehicle', 'make', 'text'),
        ('vehicle', 'model', 'text'),
        ('vehicle', 'year', 'bigint'),
        ('vehicle', 'created_at', 'timestamp without time zone'),
        ('vehicle_assignment', 'assignment_id', 'bigint'),
        ('vehicle_assignment', 'vehicle_id', 'bigint'),
        ('vehicle_assignment', 'driver_id', 'bigint'),
        ('vehicle_assignment', 'assigned_from', 'timestamp without time zone'),
        ('vehicle_assignment', 'assigned_to', 'timestamp without time zone'),
        ('parking_area', 'parking_area_id', 'bigint'),
        ('parking_area', 'name', 'text'),
        ('parking_area', 'capacity', 'bigint'),
        ('parking_area', 'geom', 'geometry(polygon,4326)'),
        ('parking_area', 'created_at', 'timestamp without time zone'),
        ('road_segment', 'road_id', 'bigint'),
        ('road_segment', 'name', 'text'),
        ('road_segment', 'speed_limit_kph', 'bigint'),
        ('road_segment', 'geom', 'geometry(linestring,4326)'),
        ('road_segment', 'created_at', 'timestamp without time zone'),
        ('road_segment', 'is_oneway', 'boolean'),
        ('road_segment', 'direction', 'text'),
        ('location_ping', 'ping_id', 'bigint'),
        ('location_ping', 'vehicle_id', 'bigint'),
        ('location_ping', 'ts', 'timestamp without time zone'),
        ('location_ping', 'geom', 'geometry(point,4326)'),
        ('location_ping', 'speed_kph', 'double precision'),
        ('location_ping', 'heading_deg', 'double precision'),
        ('trip', 'trip_id', 'bigint'),
        ('trip', 'vehicle_id', 'bigint'),
        ('trip', 'start_ts', 'timestamp without time zone'),
        ('trip', 'end_ts', 'timestamp without time zone'),
        ('trip', 'start_geom', 'geometry(point,4326)'),
        ('trip', 'end_geom', 'geometry(point,4326)'),
        ('trip', 'distance_km', 'double precision')
),
expected_tables AS (
    SELECT DISTINCT table_name FROM expected_columns
),
expected_primary_keys (table_name, column_name) AS (
    VALUES
        ('fuel_type', 'fuel_type_id'),
        ('vehicle_kind', 'vehicle_kind_id'),
        ('vehicle_status', 'vehicle_status_id'),
        ('driver', 'driver_id'),
        ('vehicle_type', 'vehicle_type_id'),
        ('vehicle', 'vehicle_id'),
        ('vehicle_assignment', 'assignment_id'),
        ('parking_area', 'parking_area_id'),
        ('road_segment', 'road_id'),
        ('location_ping', 'ping_id'),
        ('trip', 'trip_id')
),
expected_foreign_keys (table_name, column_name, referenced_table, referenced_column) AS (
    VALUES
        ('vehicle_type', 'vehicle_kind_id', 'vehicle_kind', 'vehicle_kind_id'),
        ('vehicle_type', 'fuel_type_id', 'fuel_type', 'fuel_type_id'),
        ('vehicle', 'vehicle_type_id', 'vehicle_type', 'vehicle_type_id'),
        ('vehicle', 'vehicle_status_id', 'vehicle_status', 'vehicle_status_id'),
        ('vehicle_assignment', 'vehicle_id', 'vehicle', 'vehicle_id'),
        ('vehicle_assignment', 'driver_id', 'driver', 'driver_id'),
        ('location_ping', 'vehicle_id', 'vehicle', 'vehicle_id'),
        ('trip', 'vehicle_id', 'vehicle', 'vehicle_id')
),
expected_geometry (table_name, column_name, geometry_type, srid, dimensions) AS (
    VALUES
        ('parking_area', 'geom', 'POLYGON', 4326, 2),
        ('road_segment', 'geom', 'LINESTRING', 4326, 2),
        ('location_ping', 'geom', 'POINT', 4326, 2),
        ('trip', 'start_geom', 'POINT', 4326, 2),
        ('trip', 'end_geom', 'POINT', 4326, 2)
),
actual_tables AS (
    SELECT relation.oid, relation.relname::text AS table_name
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relkind IN ('r', 'p', 'f')
      AND NOT EXISTS (
          SELECT 1
          FROM pg_catalog.pg_depend AS dependency
          WHERE dependency.classid = 'pg_catalog.pg_class'::regclass
            AND dependency.objid = relation.oid
            AND dependency.deptype = 'e'
      )
),
actual_columns AS (
    SELECT
        relation.table_name,
        attribute.attname::text AS column_name,
        lower(pg_catalog.format_type(attribute.atttypid, attribute.atttypmod)) AS data_type
    FROM actual_tables AS relation
    JOIN pg_catalog.pg_attribute AS attribute ON attribute.attrelid = relation.oid
    WHERE attribute.attnum > 0
      AND NOT attribute.attisdropped
),
actual_keys AS (
    SELECT
        relation.table_name,
        constraint_info.contype AS key_type,
        constraint_info.convalidated AS validated,
        ARRAY(
            SELECT attribute.attname::text
            FROM unnest(constraint_info.conkey) WITH ORDINALITY AS key_column(attnum, position)
            JOIN pg_catalog.pg_attribute AS attribute
                ON attribute.attrelid = constraint_info.conrelid
               AND attribute.attnum = key_column.attnum
            ORDER BY key_column.position
        ) AS column_names,
        referenced_namespace.nspname::text AS referenced_schema,
        referenced_relation.relname::text AS referenced_table,
        ARRAY(
            SELECT attribute.attname::text
            FROM unnest(constraint_info.confkey) WITH ORDINALITY AS key_column(attnum, position)
            JOIN pg_catalog.pg_attribute AS attribute
                ON attribute.attrelid = constraint_info.confrelid
               AND attribute.attnum = key_column.attnum
            ORDER BY key_column.position
        ) AS referenced_columns
    FROM actual_tables AS relation
    JOIN pg_catalog.pg_constraint AS constraint_info ON constraint_info.conrelid = relation.oid
    LEFT JOIN pg_catalog.pg_class AS referenced_relation ON referenced_relation.oid = constraint_info.confrelid
    LEFT JOIN pg_catalog.pg_namespace AS referenced_namespace ON referenced_namespace.oid = referenced_relation.relnamespace
    WHERE constraint_info.contype IN ('p', 'f')
),
expected_objects (check_name, definition) AS (
    SELECT 'Tables', jsonb_build_array(table_name) FROM expected_tables
    UNION ALL
    SELECT 'Columns and types', jsonb_build_array(table_name, column_name, data_type)
    FROM expected_columns
    UNION ALL
    SELECT 'Primary keys', jsonb_build_array(table_name, ARRAY[column_name], true)
    FROM expected_primary_keys
    UNION ALL
    SELECT 'Foreign keys', jsonb_build_array(
        table_name, ARRAY[column_name], 'public'::text,
        referenced_table, ARRAY[referenced_column], true
    )
    FROM expected_foreign_keys
    UNION ALL
    SELECT 'Geometry and SRID', jsonb_build_array(table_name, column_name, geometry_type, srid, dimensions)
    FROM expected_geometry
),
actual_objects (check_name, definition) AS (
    SELECT 'Tables', jsonb_build_array(table_name) FROM actual_tables
    UNION ALL
    SELECT 'Columns and types', jsonb_build_array(table_name, column_name, data_type)
    FROM actual_columns
    UNION ALL
    SELECT 'Primary keys', jsonb_build_array(table_name, column_names, validated)
    FROM actual_keys WHERE key_type = 'p'
    UNION ALL
    SELECT 'Foreign keys', jsonb_build_array(
        table_name, column_names, referenced_schema,
        referenced_table, referenced_columns, validated
    )
    FROM actual_keys WHERE key_type = 'f'
    UNION ALL
    SELECT 'Geometry and SRID', jsonb_build_array(
        geometry_info.f_table_name, geometry_info.f_geometry_column,
        geometry_info.type, geometry_info.srid, geometry_info.coord_dimension
    )
    FROM public.geometry_columns AS geometry_info
    JOIN actual_tables AS relation ON relation.table_name = geometry_info.f_table_name
    WHERE geometry_info.f_table_schema = 'public'
),
differences AS (
    (SELECT * FROM expected_objects EXCEPT ALL SELECT * FROM actual_objects)
    UNION ALL
    (SELECT * FROM actual_objects EXCEPT ALL SELECT * FROM expected_objects)
),
checks (display_order, check_name) AS (
    VALUES
        (1, 'Tables'),
        (2, 'Columns and types'),
        (3, 'Primary keys'),
        (4, 'Foreign keys'),
        (5, 'Geometry and SRID')
)
SELECT
    checks.check_name,
    (SELECT count(*) FROM expected_objects WHERE check_name = checks.check_name) AS expected,
    (SELECT count(*) FROM actual_objects WHERE check_name = checks.check_name) AS actual,
    CASE WHEN EXISTS (
        SELECT 1 FROM differences WHERE check_name = checks.check_name
    ) THEN 'FAIL' ELSE 'PASS' END AS status,
    (SELECT count(*) FROM differences WHERE check_name = checks.check_name) AS differences
FROM checks
ORDER BY checks.display_order;

\echo Geometry definitions: expect five rows, all with SRID 4326 and two dimensions
SELECT
    f_table_name AS table_name,
    f_geometry_column AS column_name,
    type AS geometry_type,
    srid,
    coord_dimension AS dimensions
FROM public.geometry_columns
WHERE f_table_schema = 'public'
  AND f_table_name IN ('parking_area', 'road_segment', 'location_ping', 'trip')
ORDER BY f_table_name, f_geometry_column;
