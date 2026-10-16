"""Expected database types and relationships from the project diagram."""

COLUMN_TYPES = {
    "fuel_type_id": "bigint", "vehicle_kind_id": "bigint", "vehicle_status_id": "bigint",
    "driver_id": "bigint", "vehicle_type_id": "bigint", "vehicle_id": "bigint",
    "assignment_id": "bigint", "parking_area_id": "bigint", "road_id": "bigint",
    "ping_id": "bigint", "trip_id": "bigint", "year": "bigint", "capacity": "bigint",
    "speed_limit_kph": "bigint", "name": "text", "first_name": "text",
    "last_name": "text", "license_number": "text", "plate_number": "text",
    "make": "text", "model": "text", "direction": "text", "is_oneway": "boolean",
    "emissions_rating": "double precision", "speed_kph": "double precision",
    "heading_deg": "double precision", "distance_km": "double precision",
    "hired_at": "timestamp without time zone", "created_at": "timestamp without time zone",
    "assigned_from": "timestamp without time zone", "assigned_to": "timestamp without time zone",
    "ts": "timestamp without time zone", "start_ts": "timestamp without time zone",
    "end_ts": "timestamp without time zone",
}

GEOMETRY_TYPES = {
    "parking_area": {"geom": "geometry(Polygon,4326)"},
    "road_segment": {"geom": "geometry(LineString,4326)"},
    "location_ping": {"geom": "geometry(Point,4326)"},
    "trip": {"start_geom": "geometry(Point,4326)", "end_geom": "geometry(Point,4326)"},
}

FOREIGN_KEYS = (
    ("vehicle_type", "vehicle_kind_id", "vehicle_kind", "vehicle_kind_id"),
    ("vehicle_type", "fuel_type_id", "fuel_type", "fuel_type_id"),
    ("vehicle", "vehicle_type_id", "vehicle_type", "vehicle_type_id"),
    ("vehicle", "vehicle_status_id", "vehicle_status", "vehicle_status_id"),
    ("vehicle_assignment", "vehicle_id", "vehicle", "vehicle_id"),
    ("vehicle_assignment", "driver_id", "driver", "driver_id"),
    ("location_ping", "vehicle_id", "vehicle", "vehicle_id"),
    ("trip", "vehicle_id", "vehicle", "vehicle_id"),
)
