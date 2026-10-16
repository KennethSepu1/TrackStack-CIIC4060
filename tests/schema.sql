-- Test schema for the seven tables supported by this stage.
CREATE TABLE public.fuel_type (
    fuel_type_id bigint PRIMARY KEY,
    name text
);

CREATE TABLE public.vehicle_kind (
    vehicle_kind_id bigint PRIMARY KEY,
    name text
);

CREATE TABLE public.vehicle_status (
    vehicle_status_id bigint PRIMARY KEY,
    name text
);

CREATE TABLE public.driver (
    driver_id bigint PRIMARY KEY,
    first_name text,
    last_name text,
    license_number text,
    hired_at timestamp
);

CREATE TABLE public.vehicle_type (
    vehicle_type_id bigint PRIMARY KEY,
    vehicle_kind_id bigint REFERENCES public.vehicle_kind(vehicle_kind_id),
    fuel_type_id bigint REFERENCES public.fuel_type(fuel_type_id),
    emissions_rating double precision,
    created_at timestamp
);

CREATE TABLE public.vehicle (
    vehicle_id bigint PRIMARY KEY,
    vehicle_type_id bigint REFERENCES public.vehicle_type(vehicle_type_id),
    vehicle_status_id bigint REFERENCES public.vehicle_status(vehicle_status_id),
    plate_number text,
    make text,
    model text,
    year bigint,
    created_at timestamp
);

CREATE TABLE public.vehicle_assignment (
    assignment_id bigint PRIMARY KEY,
    vehicle_id bigint REFERENCES public.vehicle(vehicle_id),
    driver_id bigint REFERENCES public.driver(driver_id),
    assigned_from timestamp,
    assigned_to timestamp
);
