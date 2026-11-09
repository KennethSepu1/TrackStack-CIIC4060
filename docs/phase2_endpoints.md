# Phase II Endpoints

Source: `p2specsFall2026.pdf`. Base path `/api/v1`, schema `projectfall2026`. Field names and status codes follow the spec. Where the spec is silent, the row says so.

## Endpoints

| Method | Path | Required fields or params | Success | Errors | Response shape |
| ------ | ---- | ------------------------- | ------- | ------ | -------------- |
| POST | `/api/v1/vehicles` | Body: `vehicle_type_id` (must exist), `vehicle_status_id` (must exist), `plate_number` (non-empty, unique). Optional: `make`, `model` (trimmed), `year` (1950 to 2100) | 201 | 400, 404, 409 | `{vehicle_id, vehicle_type_id, vehicle_status_id, plate_number, make, model, year, created_at}` |
| GET | `/api/v1/vehicles` | None. Query: `limit`, `offset` (non-negative integers), `status` (name or ID), `plate_number` (partial match) | 200 | 400 | `{items: [{vehicle_id, plate_number, make, model, year, vehicle_type_id, vehicle_status_id, created_at}], limit, offset, count}` |
| GET | `/api/v1/vehicles/{vehicle_id}` | Path: `vehicle_id` (positive integer) | 200 | 404 | `{vehicle_id, vehicle_type_id, vehicle_status_id, plate_number, make, model, year, created_at}` |
| PUT | `/api/v1/vehicles/{vehicle_id}` | Path: `vehicle_id`. Body: at least one of `vehicle_type_id` (must exist), `vehicle_status_id` (must exist), `plate_number` (unique), `make`, `model`, `year` (1950 to 2100) | 200 | 400, 404, 409 | `{vehicle_id, vehicle_type_id, vehicle_status_id, plate_number, make, model, year, created_at}` |
| DELETE | `/api/v1/vehicles/{vehicle_id}` | Path: `vehicle_id` (must exist). No cascade: a vehicle referenced by `location_ping`, `trip` or `vehicle_assignment` returns 409 | 200 | 404, 409 | `{message: "Vehicle deleted successfully.", vehicle_id}` |
| GET | `/api/v1/vehicles/{vehicle_id}/current-location` | Path: `vehicle_id` (positive integer). `last_geom` is a GeoJSON Point, EPSG:4326, [lon, lat] | 200, or 204 with no pings | 400, 404 | `{vehicle_id, plate_number, status, vehicle_kind, fuel_type, emissions_rating, last_ts, last_geom: Point, speed_kph, heading_deg}` |
| POST | `/api/v1/road-segments` | Body: `name` (non-empty), `geom` (valid LineString, SRID 4326). Optional: `speed_limit_kph` (>= 0), `is_oneway`, `direction` (`both` or `forward`) | 201 | 400 | `{road_id, name, speed_limit_kph, is_oneway, direction, geom, created_at}` |
| GET | `/api/v1/road-segments` | None. Query: `limit`, `offset` (non-negative integers), `name`, speed range, `bbox` (four numbers minLon,minLat,maxLon,maxLat, WGS84 ranges, min < max) | 200 (not listed in spec) | 400 (not listed in spec) | `{items: [{road_id, name, speed_limit_kph, created_at}], limit, offset, count}` |
| GET | `/api/v1/road-segments/{road_id}` | Path: `road_id` (positive integer) | 200 | 404 | `{road_id, name, speed_limit_kph, geom, created_at}` |
| PUT | `/api/v1/road-segments/{road_id}` | Path: `road_id`. Body: at least one of `name`, `speed_limit_kph` (>= 0), `is_oneway`, `direction`, `geom` (valid LineString, SRID 4326) | 200 | 400, 404 | `{road_id, name, speed_limit_kph, geom, created_at}` |
| DELETE | `/api/v1/road-segments/{road_id}` | Path: `road_id` (must exist) | 200 | 404 | `{message: "Road segment deleted successfully.", road_id}` |
| GET | `/api/v1/road-segments/geojson` | None. Query: `limit`, `offset` (non-negative integers), `name` (case-insensitive partial match), `min_speed_kph`, `max_speed_kph` (`min_speed_kph` <= `max_speed_kph`). No `bbox` | 200 | 400, 422, 500 | `application/geo+json`: `{type: "FeatureCollection", count, limit, offset, features: [{type: "Feature", geometry: LineString, properties: {road_id, name, speed_limit_kph, is_oneway, direction, created_at}}]}` |
| POST | `/api/v1/parking-areas` | Body: `name` (non-empty), `geom` (valid closed Polygon, SRID 4326). Optional: `capacity` (>= 0) | 201 | 400 | `{parking_area_id, name, capacity, geom, created_at}` |
| GET | `/api/v1/parking-areas` | None. Query: `limit`, `offset` (non-negative integers), `name`, `bbox` (four numbers minLon,minLat,maxLon,maxLat, WGS84 ranges, min < max) | 200 | 400 | `{items: [{parking_area_id, name, capacity, created_at}], limit, offset, count}` |
| GET | `/api/v1/parking-areas/{parking_area_id}` | Path: `parking_area_id` (positive integer) | 200 | 404 | `{parking_area_id, name, capacity, geom, created_at}` |
| PUT | `/api/v1/parking-areas/{parking_area_id}` | Path: `parking_area_id`. Body: at least one of `name`, `capacity` (>= 0), `geom` (valid Polygon, SRID 4326) | 200 | 400, 404 | `{parking_area_id, name, capacity, geom, created_at}` |
| DELETE | `/api/v1/parking-areas/{parking_area_id}` | Path: `parking_area_id` (must exist) | 200 | 404 | `{message: "Parking area deleted successfully.", parking_area_id}` |
| POST | `/api/v1/location-pings` | Body: `vehicle_id` (must exist), `ts` (valid timestamp), `geom` (valid Point, SRID 4326). Optional: `speed_kph` (>= 0), `heading_deg` (>= 0 and < 360) | 201 | 400, 404 | `{ping_id, vehicle_id, ts, geom, speed_kph, heading_deg}` |
| GET | `/api/v1/location-pings` | None. Query: `limit`, `offset` (non-negative integers), `vehicle_id` (positive integer), `from_ts`, `to_ts` (valid timestamps, `from_ts` <= `to_ts`), `bbox` (four numbers minLon,minLat,maxLon,maxLat, WGS84 ranges, min < max) | 200 | 400 | `{items: [{ping_id, vehicle_id, ts, speed_kph, heading_deg}], limit, offset, count}` |
| GET | `/api/v1/location-pings/{ping_id}` | Path: `ping_id` (positive integer) | 200 | 404 | `{ping_id, vehicle_id, ts, geom, speed_kph, heading_deg}` |
| PUT | `/api/v1/location-pings/{ping_id}` | Path: `ping_id`. Body: at least one of `vehicle_id` (must exist), `ts`, `geom` (valid Point, SRID 4326), `speed_kph` (>= 0), `heading_deg` (>= 0 and < 360) | 200 | 400, 404 | `{ping_id, vehicle_id, ts, geom, speed_kph, heading_deg}` |
| DELETE | `/api/v1/location-pings/{ping_id}` | Path: `ping_id` (must exist) | 200 | 404 | `{message: "Location ping deleted successfully.", ping_id}` |
| GET | `/api/v1/vehicles/{vehicle_id}/pings` | Path: `vehicle_id` (must exist). Query: `limit`, `offset` (non-negative integers), `from_ts`, `to_ts` (valid timestamps, `from_ts` <= `to_ts`) | 200 | 400, 404 | `{vehicle_id, items: [{ping_id, ts, geom, speed_kph, heading_deg}], limit, offset, count}` |
| POST | `/api/v1/trips` | Body: `vehicle_id` (must exist), `start_ts`, `end_ts` (`end_ts` later than `start_ts`). Optional: `start_geom`, `end_geom` (valid Point, SRID 4326), `distance_km` (>= 0) | 201 | 400, 404 | `{trip_id, vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km}` |
| GET | `/api/v1/trips` | None. Query: `limit`, `offset` (non-negative integers), `vehicle_id` (positive integer), `from_ts`, `to_ts` (valid timestamps, `from_ts` <= `to_ts`) | 200 | 400 | `{items: [{trip_id, vehicle_id, start_ts, end_ts, distance_km}], limit, offset, count}` |
| GET | `/api/v1/trips/{trip_id}` | Path: `trip_id` (positive integer) | 200 | 404 | `{trip_id, vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km}` |
| PUT | `/api/v1/trips/{trip_id}` | Path: `trip_id`. Body: at least one of `vehicle_id` (must exist), `start_ts`, `end_ts` (after the update, `end_ts` later than `start_ts`), `start_geom`, `end_geom` (valid Point, SRID 4326), `distance_km` (>= 0) | 200 | 400, 404, 422 | `{trip_id, vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km}` |
| DELETE | `/api/v1/trips/{trip_id}` | Path: `trip_id` (must exist) | 200 | 404 | `{message: "Trip deleted successfully.", trip_id}` |
| GET | `/api/v1/vehicles/{vehicle_id}/trips` | Path: `vehicle_id` (must exist). Query: `limit`, `offset` (non-negative integers), `from_ts`, `to_ts` (valid timestamps, `from_ts` <= `to_ts`) | 200 | 400, 404 | `{vehicle_id, items: [{trip_id, start_ts, end_ts, distance_km}], limit, offset, count}` |
| POST | `/api/v1/drivers` | Body: `first_name`, `last_name` (trimmed, non-empty), `license_number` (trimmed, non-empty, unique), `hired_at` (RFC 3339) | 201 | 400, 409, 422 | `{driver_id, first_name, last_name, license_number, hired_at}` |
| GET | `/api/v1/drivers` | None. Query: `limit`, `offset` (non-negative integers), `name` (case-insensitive partial match on `first_name` and `last_name`), `license_number` (case-insensitive partial match) | 200 | 400 | `{items: [{driver_id, first_name, last_name, license_number, hired_at}], limit, offset, count}` |
| GET | `/api/v1/drivers/{driver_id}` | Path: `driver_id` (positive integer) | 200 | 404 | `{driver_id, first_name, last_name, license_number, hired_at}` |
| PUT | `/api/v1/drivers/{driver_id}` | Path: `driver_id`. Body: at least one of `first_name`, `last_name` (non-empty after trimming), `license_number` (non-empty after trimming, unique), `hired_at` (RFC 3339) | 200 | 400, 404, 409, 422 | `{driver_id, first_name, last_name, license_number, hired_at}` |
| DELETE | `/api/v1/drivers/{driver_id}` | Path: `driver_id` (must exist). A driver referenced by an assignment returns 409 | 200 | 404, 409 | `{message: "Driver deleted successfully.", driver_id}` |
| POST | `/api/v1/vehicle-assignments` | Body: `vehicle_id`, `driver_id` (positive integers, must exist), `assigned_from` (RFC 3339). Optional: `assigned_to` (later than `assigned_from`; null means active) | 201 | 400, 404, 422 | `{assignment_id, vehicle_id, driver_id, assigned_from, assigned_to}` |
| GET | `/api/v1/vehicle-assignments` | None. Query: `limit`, `offset` (non-negative integers), `vehicle_id`, `driver_id` (positive integers), `active` (`true` means `assigned_to` is null, `false` means closed). Filters combine with AND | 200 | 400 | `{items: [{assignment_id, vehicle_id, driver_id, assigned_from, assigned_to}], limit, offset, count}` |
| GET | `/api/v1/vehicle-assignments/{assignment_id}` | Path: `assignment_id` (positive integer) | 200 | 404 | `{assignment_id, vehicle_id, driver_id, assigned_from, assigned_to}` |
| PUT | `/api/v1/vehicle-assignments/{assignment_id}` | Path: `assignment_id`. Body: at least one of `vehicle_id`, `driver_id` (not null, must exist), `assigned_from` (not null), `assigned_to` (after the update, null or later than `assigned_from`) | 200 | 400, 404, 422 | `{assignment_id, vehicle_id, driver_id, assigned_from, assigned_to}` |
| DELETE | `/api/v1/vehicle-assignments/{assignment_id}` | Path: `assignment_id` (must exist) | 200 | 404 | `{message: "Vehicle assignment deleted successfully.", assignment_id}` |

Spec notes:

- Each PUT cell lists only the rules the spec gives for that PUT. Null handling on PUT is covered under Edge cases.
- The spec puts the bbox rule under `GET /api/v1/road-segments/{road_id}`, but it applies to the list endpoint, because the by-ID route takes no `bbox`.

- The spec gives no status table for `GET /api/v1/road-segments`. The 200 and 400 in that row follow the other list endpoints. The spec names the speed range filter but not its parameters. The DAO uses `min_speed_kph` and `max_speed_kph`, the same names as the GeoJSON route.
- GET and PUT road-segment responses contain only `road_id`, `name`, `speed_limit_kph`, `geom`, and `created_at`. POST and GeoJSON also include `is_oneway` and `direction`.
- The vehicle list example sends `limit=0`, but its response shows `"limit": 20`, so the spec doesn't settle what `limit=0` returns. The proposed answer is to accept it, since it's a non-negative integer, and return `"items": []`, `"limit": 0` and the full `count`. The team should confirm.
- `status` on `GET /api/v1/vehicles` may be a status name or a status ID. The DAO accepts both.

## Edge cases

### Point validation on pings and trips

`normalize_geometry` in `backend/dao/_geometry.py` only handles LineString and Polygon and raises for `Point`. The ping and trip DAOs send `geom` straight to `ST_GeomFromGeoJSON` with no checks. The handler has to validate Points itself.

A valid Point:

- is a JSON object with `type` exactly `"Point"`
- has `coordinates` as exactly two numbers, `[longitude, latitude]`
- has longitude in [-180, 180] and latitude in [-90, 90]
- has no `crs` member
- doesn't use booleans as numbers. `true` counts as `1` in Python, so check types strictly.

| Field | POST | PUT | Status on failure |
| ----- | ---- | --- | ----------------- |
| ping `geom` | Required | Optional, not null | 400 |
| trip `start_geom`, `end_geom` | Optional, may be null | Optional, may be null | 400 on POST, 422 on PUT |

Cases to test: `LineString` type, one coordinate, three coordinates, a string coordinate, longitude 200, latitude -95, missing `coordinates`, and `geom` as a string.

### bbox validation

The `bbox` parameter is accepted on `GET /api/v1/road-segments`, `GET /api/v1/parking-areas` and `GET /api/v1/location-pings`. The GeoJSON route rejects it with HTTP 400.

- Format is `bbox=minLon,minLat,maxLon,maxLat`, with exactly four comma-separated values that are finite numbers.
- Longitude must be in [-180, 180] and latitude in [-90, 90].
- `minLon < maxLon` and `minLat < maxLat`, both strict. Equal values return 400.
- Any failure returns 400.
- A row matches if its geometry is inside, touches or crosses the box. That means `ST_Intersects(geom, ST_MakeEnvelope(minLon, minLat, maxLon, maxLat, 4326))`, not `ST_Within` or `ST_Contains`. All three list DAOs already use `ST_Intersects`. A ping lying exactly on the box edge is returned, and so is a road that only crosses through the box.
- Cases to test: `-67.2100,18.1800,-67.1200,18.2600` passes. These fail: three values, five values, `a,b,c,d`, `minLon = maxLon`, min and max swapped, latitude 91, and longitude -181.

### Rejecting null on PUT for required fields

An omitted key means leave the column unchanged. `"field": null` means set it to null. The handler must tell these apart: with Pydantic, use `model_dump(exclude_unset=True)`, not `exclude_none=True`. The schema has no `NOT NULL` constraints, so the database will store a null that slips through.

| Resource | Cannot be null on PUT | Status | May be null |
| -------- | --------------------- | ------ | ----------- |
| vehicles | `vehicle_type_id`, `vehicle_status_id`, `plate_number` | 400 | `make`, `model`, `year` |
| road-segments | `name`, `geom` | 400 | `speed_limit_kph`, `is_oneway`, `direction` |
| parking-areas | `name`, `geom` | 400 | `capacity` |
| location-pings | `vehicle_id`, `ts`, `geom` | 400 | `speed_kph`, `heading_deg` |
| trips | `vehicle_id`, `start_ts`, `end_ts` | 422 | `start_geom`, `end_geom`, `distance_km` |
| drivers | `first_name`, `last_name`, `license_number`, `hired_at` | 422 | none |
| vehicle-assignments | `vehicle_id`, `driver_id`, `assigned_from` | 400 for the IDs, 422 for `assigned_from` | `assigned_to` |

The rule: use 422 where the endpoint lists 422 for an invalid field (PUT trips, PUT drivers), otherwise 400. For assignments, the spec only lists 422 for an invalid interval. A null `assigned_from` breaks the interval and the DAO raises `InvalidAssignmentTimeError`, so that one is 422. Null IDs are 400. The spec doesn't settle this, so the team should confirm it.

`{}`, or a body with only unknown keys, returns 400 on every PUT.

### Trip end before start

- `end_ts` must be strictly later than `start_ts`. Equal times are invalid.
- `POST /api/v1/trips` returns 400, because 422 is not listed for that endpoint.
- `PUT /api/v1/trips/{trip_id}` returns 422. When only one of the two times is sent, check it against the stored value. Example: the stored trip runs 08:00 to 08:45 and the PUT body is `{"start_ts": "2026-03-14T09:00:00Z"}`. That returns 422.
- The DAO raises `InvalidTripTimeError` in both cases, and the handler picks the code from the route.
- For comparison, vehicle assignments return 422 for an invalid interval on both POST and PUT.

### RFC 3339 timestamps with Z

- Every timestamp in a response ends in `Z`, for example `2026-03-14T10:00:00Z`. That applies to `created_at`, `last_ts`, `ts`, `start_ts`, `end_ts`, `hired_at`, `assigned_from` and `assigned_to`; a null `assigned_to` stays `null`. Some spec examples leave out the `Z` (PUT vehicle `created_at`, the road segment and parking area `created_at`, and the POST ping `ts`). Rule 4 and "Use RFC 3339 format for every timestamp" take precedence.
- The DAOs return naive `datetime` values from `TIMESTAMP` columns, and FastAPI serializes them without `Z`. The handler has to format them.
- On input, accept both `Z` and explicit offsets. Convert to UTC, drop `tzinfo`, and pass a naive value to the DAO. For example, `2026-03-14T11:30:00-04:00` is stored as `2026-03-14 15:30:00` and returned as `2026-03-14T15:30:00Z`.
- Input timestamps require `Z` or a valid numeric timezone offset. Fractional seconds are truncated to microsecond precision for storage.
- A timestamp that doesn't parse, such as `2026-13-01T00:00:00Z` or `yesterday`, returns 422 on POST and PUT drivers and assignments and on PUT trips. Pings, POST trips, and time filters return 400.
- `from_ts` later than `to_ts` returns 400. Equal values are allowed.

### 204 with no body on current-location

- The order of checks:
  1. `vehicle_id` that isn't a positive integer: 400.
  2. Vehicle doesn't exist: 404.
  3. Vehicle exists but has no pings: 204.
  4. Otherwise: 200.
- A 204 has no body at all, not even JSON `null`. Return `Response(status_code=204)`. Returning `None` from a JSON route sends `null`.
- `get_current_location` returns `None` when the vehicle is missing. When the vehicle has no pings, it returns a row whose `last_ts` and `last_geom` are `None`.
- This is the only by-ID endpoint that lists 400 for a bad path ID.

### application/geo+json on the GeoJSON route

- The `Content-Type` must be `application/geo+json`. Use `JSONResponse(content, media_type="application/geo+json")`, because the default `application/json` fails the endpoint.
- `created_at` inside `properties` comes back as a `datetime`. Convert it to a `Z` string first, because `JSONResponse` can't serialize `datetime`.
- Register `/road-segments/geojson` before `/road-segments/{road_id}`. Otherwise `geojson` is matched as a `road_id`.
- `min_speed_kph > max_speed_kph` returns 400. A type or range failure such as `limit=-1` or `min_speed_kph=abc` returns 422. A database failure returns 500.
- `count` is the number of matches before pagination. `get_road_segments_geojson` already computes it.

## DAO gaps a handler must cover

### All handlers

1. Every DAO exception subclasses `ValueError`, so catch the specific ones before plain `ValueError`.

   | Exception | Status |
   | --------- | ------ |
   | `DuplicatePlateError` | 409 |
   | `InvalidVehicleReferenceError` | 404 |
   | `VehicleInUseError` | 409 |
   | `InvalidPingVehicleError` | 404 |
   | `InvalidTripVehicleError` | 404 |
   | `InvalidTripTimeError` | 400 on POST, 422 on PUT |
   | `DuplicateLicenseError` | 409 |
   | `DriverInUseError` | 409 |
   | `InvalidAssignmentReferenceError` | 404 |
   | `InvalidAssignmentTimeError` | 422 |
   | `ValueError` | 400; 422 for PUT trips and for driver field errors |

2. FastAPI returns 422 for malformed JSON and for request-model validation errors. Most endpoints list 400 for these, so add a `RequestValidationError` handler that returns 400. Then return 422 explicitly where the spec lists it: drivers, assignment intervals, PUT trips, and the GeoJSON query checks.
3. Empty PUT bodies and unknown keys make the DAOs raise plain `ValueError`. Check for them in the handler first so they return 400, even on drivers and trips, where a DAO `ValueError` otherwise maps to 422.
4. `get_*`, `update_*` and `delete_*` return `None` for a missing ID. That's a 404.
5. No DAO checks path IDs. The spec says they must be positive integers, but only current-location lists 400. On the other endpoints, 404 for zero or negative IDs is consistent with "does not exist". The team should confirm.
6. Only the road segment and parking area DAOs check `limit` and `offset`, through `list_parameters`. Every other list handler has to reject negative or non-integer values with 400.
7. Fill `count` with the matching `count_*` method from PR #21, not `len(items)`. Each one uses the same filter SQL as its list and returns the number of matches before pagination. Pass it the same filter arguments as the list call, without `limit` and `offset`.

   | List endpoint | List method | Count method |
   | ------------- | ----------- | ------------ |
   | `GET /api/v1/vehicles` | `list_vehicles` | `count_vehicles` |
   | `GET /api/v1/road-segments` | `list_road_segments` | `count_road_segments` |
   | `GET /api/v1/parking-areas` | `list_parking_areas` | `count_parking_areas` |
   | `GET /api/v1/location-pings` | `list_location_pings` | `count_location_pings` |
   | `GET /api/v1/vehicles/{vehicle_id}/pings` | `list_vehicle_pings` | `count_vehicle_pings` |
   | `GET /api/v1/trips` | `list_trips` | `count_trips` |
   | `GET /api/v1/vehicles/{vehicle_id}/trips` | `list_vehicle_trips` | `count_vehicle_trips` |
   | `GET /api/v1/drivers` | `list_drivers` | `count_drivers` |
   | `GET /api/v1/vehicle-assignments` | `list_vehicle_assignments` | `count_vehicle_assignments` |

   `count_vehicle_pings` and `count_vehicle_trips` return `None` when the vehicle doesn't exist, like their list methods, which is a 404. `GET /api/v1/road-segments/geojson` needs no extra call, because `get_road_segments_geojson` already returns `count`.
8. Timestamps go in and out as described under RFC 3339 above. The driver and assignment DAOs reject timezone-aware datetimes. If one reaches `create_trip` or `update_trip`, comparing it with a naive datetime raises `TypeError`, which becomes a 500.
9. The vehicle, ping and trip DAOs don't type-check their inputs. Use strict types so that `"5"` or `true` is rejected, not converted.

### vehicle.py

- `create_vehicle` checks almost nothing. The handler must:
  - require non-null `vehicle_type_id`, `vehicle_status_id` and `plate_number`. A null ID raises no foreign-key error, so the row would be inserted.
  - reject an empty or whitespace-only `plate_number`
  - check that `year` is between 1950 and 2100
  - trim `make` and `model`
- `update_vehicle` has the same gaps, plus it doesn't reject null on the required fields.
- The `status` filter accepts either a status name or a status ID. This is settled. `list_vehicles` and `count_vehicles` share the same filter: `status=active` and `status=1` return the same rows. Name matching is exact and case-sensitive, so `Active` matches nothing. The stored names are `active` and `inactive`.
- `plate_number` uses a case-sensitive partial match. `list_vehicles` doesn't check `limit` or `offset`.
- `delete_vehicle` raises `VehicleInUseError` (409) for referenced vehicles and doesn't cascade, which is what the spec requires.
- For `get_current_location`, see the 204 section above.

### road_segment.py

- It validates `name`, `speed_limit_kph`, `is_oneway`, `direction`, LineString shape and `ST_IsValid`, and raises `ValueError`, which maps to 400. Speeds must be integers, so `60.0` is rejected.
- `list_road_segments` expects `bbox` as a tuple of four numbers. The handler parses the query string, and text that isn't a number returns 400.
- For `get_road_segments_geojson`: the handler checks types and ranges first (422), then maps the DAO's `ValueError` for `min_speed_kph > max_speed_kph` to 400. A global 400 handler for validation errors must not override the 422 on this route.
- `delete_road_segment` serves `DELETE /api/v1/road-segments/{road_id}`. Nothing references `road_segment`, so there is no 409.

### parking_area.py

- It validates `name`, `capacity`, Polygon shape, closed rings and `ST_IsValid`. Errors are `ValueError`, which maps to 400. `capacity` must be an integer.
- `list_parking_areas` validates `bbox` through `normalize_bbox`. The handler still parses the query string.

### location_ping.py

- `create_location_ping` and `update_location_ping` do no validation. The handler checks:
  - `vehicle_id` is not null
  - `ts` parses
  - `geom` is a valid Point
  - `speed_kph >= 0`
  - `heading_deg` is in [0, 360)

  Invalid geometry reaches PostGIS and comes back as an unhandled database error, which is a 500.
- `list_location_pings` doesn't validate `bbox`, unlike the road segment and parking area DAOs. The handler must validate it, for example with `normalize_bbox` from `_geometry`. The handler also checks that `vehicle_id` is a positive integer and that `from_ts <= to_ts`.
- `list_vehicle_pings` returns `None` when the vehicle is missing (404) and `[]` when it has no pings in range (200 with empty `items`). The handler adds `vehicle_id` to the response.

### trip.py

- `create_trip` only checks `end_ts > start_ts` and `distance_km >= 0`. The handler checks:
  - `vehicle_id` is not null
  - both timestamps are present. A `None` causes a `TypeError`, which is a 500.
  - both geoms are valid Points
  - `distance_km` is numeric. A string causes a `TypeError`.
- `update_trip` checks the interval against stored values, `distance_km`, and a null `vehicle_id`. Its plain `ValueError` covers both an empty body and bad values. The handler sends empty bodies to 400 and everything else to 422.
- `list_trips` and `list_vehicle_trips` filter by overlap: `end_ts >= from_ts AND start_ts <= to_ts`. The spec says "time interval" without defining it, so document this in the README.

### driver.py

- It trims and checks the text fields, rejects timezone-aware `hired_at`, and enforces unique license numbers with a table lock, since the schema has no `UNIQUE` constraint. A plain `ValueError` maps to 422. Check for an empty PUT first so it returns 400.
- The duplicate check compares trimmed values and is case-sensitive.
- `list_drivers` doesn't check `limit` or `offset`.

### vehicle_assignment.py

- It checks that IDs are positive integers (`ValueError`, 400), validates the interval (`InvalidAssignmentTimeError`, 422), and maps foreign-key failures to 404.
- A timezone-aware datetime also raises `InvalidAssignmentTimeError`, so a handler that forgets to normalize would return 422 for a valid timestamp.
- `list_vehicle_assignments` needs `active` parsed to a boolean. An invalid value such as `active=maybe` returns 400, but FastAPI returns 422 by default.

## Endpoint count

| Resource | Endpoints |
| -------- | --------- |
| Vehicle | 6: five CRUD plus `current-location` |
| Road Segment | 6: five CRUD plus `geojson` |
| Parking Area | 5 |
| Location Ping | 6: five CRUD plus `/vehicles/{vehicle_id}/pings` |
| Trip | 6: five CRUD plus `/vehicles/{vehicle_id}/trips` |
| Driver | 5 |
| Vehicle Assignment | 5 |
| **Total** | **39** |

The table above has 39 rows, which matches the spec's "39 endpoints under /api/v1". The road segment DELETE is counted once.
