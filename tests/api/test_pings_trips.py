import pytest
from support import (
    INVALID_BBOXES,
    MALFORMED_BODIES,
    MISSING_ID,
    PAGE_FIELDS,
    TEST_BBOX,
    VALID_BBOX,
    assert_count_is_total,
    assert_page,
    assert_point,
    assert_utc,
    first_item,
    send_raw,
)

PING_FIELDS = {"ping_id", "vehicle_id", "ts", "geom", "speed_kph", "heading_deg"}
PING_ITEM_FIELDS = {"ping_id", "vehicle_id", "ts", "speed_kph", "heading_deg"}
VEHICLE_PING_FIELDS = {"ping_id", "ts", "geom", "speed_kph", "heading_deg"}
TRIP_FIELDS = {"trip_id", "vehicle_id", "start_ts", "end_ts", "start_geom", "end_geom", "distance_km"}
TRIP_ITEM_FIELDS = {"trip_id", "vehicle_id", "start_ts", "end_ts", "distance_km"}
VEHICLE_TRIP_FIELDS = {"trip_id", "start_ts", "end_ts", "distance_km"}
BY_VEHICLE_FIELDS = PAGE_FIELDS | {"vehicle_id"}

TS = "2026-03-14T09:58:20Z"
START_TS = "2026-03-14T08:00:00Z"
END_TS = "2026-03-14T08:45:00Z"
PING_GEOM = {"type": "Point", "coordinates": [-67.1453, 18.2011]}
START_GEOM = {"type": "Point", "coordinates": [-67.15, 18.205]}
END_GEOM = {"type": "Point", "coordinates": [-67.141, 18.21]}
BAD_POINTS = [
    {"type": "LineString", "coordinates": [[-67.1, 18.2], [-67.0, 18.3]]},
    {"type": "Polygon", "coordinates": [[[-67.1, 18.2], [-67.0, 18.2], [-67.0, 18.3], [-67.1, 18.2]]]},
    {"type": "Point", "coordinates": [-67.1]},
    {"type": "Point", "coordinates": [-67.1, 18.2, 5.0]},
    {"type": "Point", "coordinates": ["-67.1", "18.2"]},
    {"type": "Point", "coordinates": [200.0, 18.2]},
    {"type": "Point", "coordinates": [-67.1, -95.0]},
    {"type": "Point"},
    "POINT(-67.1 18.2)",
]
INVALID_TIME_QUERIES = [
    {"limit": -1},
    {"offset": -1},
    {"from_ts": "yesterday"},
    {"from_ts": "2026-03-15T00:00:00Z", "to_ts": "2026-03-14T00:00:00Z"},
]


@pytest.fixture(scope="module")
def existing_ping(api, require_route):
    return first_item(api, require_route, "/location-pings")


@pytest.fixture(scope="module")
def existing_trip(api, require_route):
    return first_item(api, require_route, "/trips")


@pytest.fixture
def make_ping(api, require_route, cleanup, make_vehicle):
    require_route("/location-pings")

    def create(**fields):
        payload = {"ts": TS, "geom": PING_GEOM, **fields}
        if "vehicle_id" not in payload:
            payload["vehicle_id"] = make_vehicle()["vehicle_id"]
        response = api.post("/location-pings", json=payload)
        body = cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 201, response.text
        return body

    return create


@pytest.fixture
def make_trip(api, require_route, cleanup, make_vehicle):
    require_route("/trips")

    def create(**fields):
        payload = {"start_ts": START_TS, "end_ts": END_TS, **fields}
        if "vehicle_id" not in payload:
            payload["vehicle_id"] = make_vehicle()["vehicle_id"]
        response = api.post("/trips", json=payload)
        body = cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 201, response.text
        return body

    return create


def assert_ping(body):
    assert set(body) == PING_FIELDS
    assert isinstance(body["ping_id"], int) and body["ping_id"] > 0
    assert_utc(body["ts"])
    assert_point(body["geom"])


def assert_trip(body):
    assert set(body) == TRIP_FIELDS
    assert isinstance(body["trip_id"], int) and body["trip_id"] > 0
    assert_utc(body["start_ts"])
    assert_utc(body["end_ts"])
    for field in ("start_geom", "end_geom"):
        if body[field] is not None:
            assert_point(body[field])


def pick(body, fields):
    return {field: body[field] for field in fields}


class TestLocationPings:
    @pytest.fixture(autouse=True)
    def pings_built(self, require_route):
        require_route("/location-pings")

    def test_list_pings(self, api):
        body = assert_page(api.get("/location-pings", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert set(item) == PING_ITEM_FIELDS
            assert_utc(item["ts"])

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/location-pings")

    @pytest.mark.parametrize("params", INVALID_TIME_QUERIES + [{"vehicle_id": 0}, {"vehicle_id": "abc"}])
    def test_list_rejects_invalid_query(self, api, params):
        assert api.get("/location-pings", params=params).status_code == 400

    @pytest.mark.parametrize("bbox", INVALID_BBOXES)
    def test_list_rejects_invalid_bbox(self, api, bbox):
        assert api.get("/location-pings", params={"bbox": bbox}).status_code == 400

    def test_list_filters_by_vehicle(self, api, existing_ping):
        params = {"vehicle_id": existing_ping["vehicle_id"], "limit": 1000}
        body = api.get("/location-pings", params=params).json()
        assert body["count"] >= 1
        assert all(item["vehicle_id"] == existing_ping["vehicle_id"] for item in body["items"])

    def test_list_filters_by_time_range(self, api, existing_ping):
        params = {"from_ts": existing_ping["ts"], "to_ts": existing_ping["ts"], "limit": 1000}
        body = api.get("/location-pings", params=params).json()
        assert existing_ping in body["items"]
        assert all(item["ts"] == existing_ping["ts"] for item in body["items"])

    def test_list_filters_by_bbox(self, api):
        everything = api.get("/location-pings", params={"limit": 1}).json()["count"]
        body = assert_page(api.get("/location-pings", params={"bbox": VALID_BBOX, "limit": 5}), 5, 0)
        assert 1 <= body["count"] <= everything

    def test_get_ping(self, api, existing_ping):
        response = api.get(f"/location-pings/{existing_ping['ping_id']}")
        assert response.status_code == 200
        body = response.json()
        assert_ping(body)
        assert pick(body, PING_ITEM_FIELDS) == existing_ping

    def test_get_missing_ping(self, api):
        assert api.get(f"/location-pings/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_create_ping(self, api, cleanup, make_vehicle):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "ts": TS,
            "geom": PING_GEOM,
            "speed_kph": 42.8,
            "heading_deg": 185.4,
        }
        response = api.post("/location-pings", json=payload)
        body = cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 201, response.text
        assert_ping(body)
        assert body == {**payload, "ping_id": body["ping_id"]}
        assert api.get(f"/location-pings/{body['ping_id']}").json() == body

    @pytest.mark.writes
    def test_create_with_required_fields_only(self, make_ping):
        body = make_ping()
        assert body["speed_kph"] is None
        assert body["heading_deg"] is None

    @pytest.mark.writes
    def test_create_normalizes_offset_timestamp(self, make_ping):
        assert make_ping(ts="2026-03-14T05:58:20-04:00")["ts"] == TS

    @pytest.mark.writes
    def test_accepts_timestamps_without_timezone_as_utc(self, api, make_ping):
        ping = make_ping(ts="2026-03-14T09:58:20")
        assert ping["ts"] == TS
        response = api.put(f"/location-pings/{ping['ping_id']}", json={"ts": "2026-03-14T10:15:00"})
        assert response.status_code == 200
        assert response.json()["ts"] == "2026-03-14T10:15:00Z"
        assert api.get(f"/location-pings/{ping['ping_id']}").json()["ts"] == "2026-03-14T10:15:00Z"
        window = {"from_ts": "2026-03-14T10:00:00", "to_ts": "2026-03-14T10:30:00"}
        response = api.get("/location-pings", params={"vehicle_id": ping["vehicle_id"], **window})
        assert response.status_code == 200
        assert [item["ping_id"] for item in response.json()["items"]] == [ping["ping_id"]]
        response = api.get(f"/vehicles/{ping['vehicle_id']}/pings", params=window)
        assert response.status_code == 200
        assert [item["ping_id"] for item in response.json()["items"]] == [ping["ping_id"]]

    @pytest.mark.writes
    @pytest.mark.parametrize("heading", [0, 359.9])
    def test_create_accepts_heading_bounds(self, make_ping, heading):
        assert make_ping(heading_deg=heading)["heading_deg"] == heading

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "ts", "geom"])
    def test_create_requires_field(self, api, cleanup, make_vehicle, field):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "ts": TS, "geom": PING_GEOM}
        del payload[field]
        response = api.post("/location-pings", json=payload)
        cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize(
        "changes",
        [{"speed_kph": -1}, {"heading_deg": -1}, {"heading_deg": 360}, {"ts": "yesterday"}],
    )
    def test_create_rejects_invalid_field(self, api, cleanup, make_vehicle, changes):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "ts": TS, "geom": PING_GEOM, **changes}
        response = api.post("/location-pings", json=payload)
        cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("geom", BAD_POINTS)
    def test_create_rejects_wrong_geometry(self, api, cleanup, make_vehicle, geom):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "ts": TS, "geom": geom}
        response = api.post("/location-pings", json=payload)
        cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 400

    @pytest.mark.writes
    def test_create_unknown_vehicle(self, api, cleanup):
        response = api.post("/location-pings", json={"vehicle_id": MISSING_ID, "ts": TS, "geom": PING_GEOM})
        cleanup.track(response, "/location-pings", "ping_id")
        assert response.status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/location-pings", content).status_code == 400

    @pytest.mark.writes
    def test_list_bbox_returns_inside_and_edge_points(self, api, make_vehicle, make_ping):
        vehicle_id = make_vehicle()["vehicle_id"]
        cases = {"inside": [-9.5, -9.5], "edge": [-10.0, -9.5], "outside": [-11.0, -11.0]}
        created = {
            case: make_ping(vehicle_id=vehicle_id, geom={"type": "Point", "coordinates": coordinates})
            for case, coordinates in cases.items()
        }
        params = {"vehicle_id": vehicle_id, "bbox": TEST_BBOX, "limit": 100}
        body = api.get("/location-pings", params=params).json()
        assert {item["ping_id"] for item in body["items"]} == {
            created["inside"]["ping_id"],
            created["edge"]["ping_id"],
        }
        assert body["count"] == 2

    @pytest.mark.writes
    def test_update_partial_changes_only_supplied_fields(self, api, make_ping):
        ping = make_ping(speed_kph=42.8, heading_deg=185.4)
        changes = {"speed_kph": 45.1, "heading_deg": 190.0}
        response = api.put(f"/location-pings/{ping['ping_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert_ping(response.json())
        assert response.json() == {**ping, **changes}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_vehicle, make_ping):
        other_vehicle = make_vehicle()
        ping = make_ping()
        changes = {
            "vehicle_id": other_vehicle["vehicle_id"],
            "ts": "2026-03-15T10:00:00Z",
            "geom": {"type": "Point", "coordinates": [-67.14, 18.21]},
            "speed_kph": 10.5,
            "heading_deg": 90.0,
        }
        response = api.put(f"/location-pings/{ping['ping_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert response.json() == {**ping, **changes}

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_ping):
        ping = make_ping()
        assert api.put(f"/location-pings/{ping['ping_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_ping, content):
        ping = make_ping()
        assert send_raw(api, "PUT", f"/location-pings/{ping['ping_id']}", content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_ping(self, api):
        assert api.put(f"/location-pings/{MISSING_ID}", json={"speed_kph": 10.0}).status_code == 404

    @pytest.mark.writes
    def test_update_unknown_vehicle(self, api, make_ping):
        ping = make_ping()
        assert api.put(f"/location-pings/{ping['ping_id']}", json={"vehicle_id": MISSING_ID}).status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize(
        "changes",
        [
            {"speed_kph": -1},
            {"heading_deg": 360},
            {"ts": "yesterday"},
            {"geom": BAD_POINTS[0]},
            {"vehicle_id": None},
            {"ts": None},
            {"geom": None},
        ],
    )
    def test_update_rejects_invalid_field(self, api, make_ping, changes):
        ping = make_ping()
        assert api.put(f"/location-pings/{ping['ping_id']}", json=changes).status_code == 400
        assert api.get(f"/location-pings/{ping['ping_id']}").json() == ping

    @pytest.mark.writes
    def test_delete_ping(self, api, make_ping):
        ping = make_ping()
        response = api.delete(f"/location-pings/{ping['ping_id']}")
        assert response.status_code == 200
        assert response.json() == {"message": "Location ping deleted successfully.", "ping_id": ping["ping_id"]}
        assert api.get(f"/location-pings/{ping['ping_id']}").status_code == 404

    @pytest.mark.writes
    def test_delete_missing_ping(self, api):
        assert api.delete(f"/location-pings/{MISSING_ID}").status_code == 404


class TestVehiclePings:
    @pytest.fixture(autouse=True)
    def vehicle_pings_built(self, require_route, existing_vehicle):
        require_route(f"/vehicles/{existing_vehicle['vehicle_id']}/pings")

    def test_vehicle_pings(self, api, existing_ping):
        vehicle_id = existing_ping["vehicle_id"]
        response = api.get(f"/vehicles/{vehicle_id}/pings", params={"limit": 5, "offset": 0})
        body = assert_page(response, 5, 0, BY_VEHICLE_FIELDS)
        assert body["vehicle_id"] == vehicle_id
        assert body["count"] >= 1
        for item in body["items"]:
            assert set(item) == VEHICLE_PING_FIELDS
            assert_utc(item["ts"])
            assert_point(item["geom"])

    def test_vehicle_pings_count_is_total_before_pagination(self, api, existing_ping):
        assert_count_is_total(api, f"/vehicles/{existing_ping['vehicle_id']}/pings")

    def test_vehicle_pings_missing_vehicle(self, api):
        assert api.get(f"/vehicles/{MISSING_ID}/pings").status_code == 404

    @pytest.mark.parametrize("params", INVALID_TIME_QUERIES)
    def test_vehicle_pings_rejects_invalid_query(self, api, existing_ping, params):
        assert api.get(f"/vehicles/{existing_ping['vehicle_id']}/pings", params=params).status_code == 400

    @pytest.mark.writes
    def test_vehicle_without_pings_returns_empty_page(self, api, make_vehicle):
        vehicle = make_vehicle()
        response = api.get(f"/vehicles/{vehicle['vehicle_id']}/pings")
        assert response.status_code == 200
        body = response.json()
        assert body["vehicle_id"] == vehicle["vehicle_id"]
        assert body["items"] == []
        assert body["count"] == 0

    @pytest.mark.writes
    def test_vehicle_pings_time_range_and_pagination(self, api, make_vehicle, make_ping):
        vehicle_id = make_vehicle()["vehicle_id"]
        pings = [
            make_ping(vehicle_id=vehicle_id, ts=f"2026-03-14T{hour}:00:00Z", speed_kph=float(hour))
            for hour in ("09", "10", "11")
        ]
        path = f"/vehicles/{vehicle_id}/pings"
        window = api.get(path, params={"from_ts": "2026-03-14T09:30:00Z", "to_ts": "2026-03-14T10:30:00Z"}).json()
        assert window["count"] == 1
        assert window["items"] == [pick(pings[1], VEHICLE_PING_FIELDS)]
        first_page = api.get(path, params={"limit": 1}).json()
        assert len(first_page["items"]) == 1
        assert first_page["count"] == 3


class TestTrips:
    @pytest.fixture(autouse=True)
    def trips_built(self, require_route):
        require_route("/trips")

    def test_list_trips(self, api):
        body = assert_page(api.get("/trips", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert set(item) == TRIP_ITEM_FIELDS
            assert_utc(item["start_ts"])
            assert_utc(item["end_ts"])

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/trips")

    @pytest.mark.parametrize("params", INVALID_TIME_QUERIES + [{"vehicle_id": 0}, {"vehicle_id": "abc"}])
    def test_list_rejects_invalid_query(self, api, params):
        assert api.get("/trips", params=params).status_code == 400

    def test_list_filters_by_vehicle(self, api, existing_trip):
        body = api.get("/trips", params={"vehicle_id": existing_trip["vehicle_id"], "limit": 1000}).json()
        assert existing_trip in body["items"]
        assert all(item["vehicle_id"] == existing_trip["vehicle_id"] for item in body["items"])

    def test_get_trip(self, api, existing_trip):
        response = api.get(f"/trips/{existing_trip['trip_id']}")
        assert response.status_code == 200
        body = response.json()
        assert_trip(body)
        assert pick(body, TRIP_ITEM_FIELDS) == existing_trip

    def test_get_missing_trip(self, api):
        assert api.get(f"/trips/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_create_trip(self, api, cleanup, make_vehicle):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "start_ts": START_TS,
            "end_ts": END_TS,
            "start_geom": START_GEOM,
            "end_geom": END_GEOM,
            "distance_km": 6.7,
        }
        response = api.post("/trips", json=payload)
        body = cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 201, response.text
        assert_trip(body)
        assert body == {**payload, "trip_id": body["trip_id"]}
        assert api.get(f"/trips/{body['trip_id']}").json() == body

    @pytest.mark.writes
    def test_create_with_required_fields_only(self, make_trip):
        body = make_trip()
        assert body["start_geom"] is None
        assert body["end_geom"] is None
        assert body["distance_km"] is None

    @pytest.mark.writes
    def test_create_normalizes_offset_timestamps(self, make_trip):
        body = make_trip(start_ts="2026-03-14T04:00:00-04:00", end_ts="2026-03-14T04:45:00-04:00")
        assert body["start_ts"] == START_TS
        assert body["end_ts"] == END_TS

    @pytest.mark.writes
    @pytest.mark.parametrize("end_ts", [START_TS, "2026-03-14T07:00:00Z"])
    def test_create_rejects_end_not_after_start(self, api, cleanup, make_vehicle, end_ts):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "start_ts": START_TS, "end_ts": end_ts}
        response = api.post("/trips", json=payload)
        cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "start_ts", "end_ts"])
    def test_create_requires_field(self, api, cleanup, make_vehicle, field):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "start_ts": START_TS, "end_ts": END_TS}
        del payload[field]
        response = api.post("/trips", json=payload)
        cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("changes", [{"distance_km": -0.1}, {"start_ts": "yesterday"}])
    def test_create_rejects_invalid_field(self, api, cleanup, make_vehicle, changes):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "start_ts": START_TS, "end_ts": END_TS, **changes}
        response = api.post("/trips", json=payload)
        cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["start_geom", "end_geom"])
    @pytest.mark.parametrize("geom", BAD_POINTS)
    def test_create_rejects_wrong_geometry(self, api, cleanup, make_vehicle, field, geom):
        payload = {"vehicle_id": make_vehicle()["vehicle_id"], "start_ts": START_TS, "end_ts": END_TS, field: geom}
        response = api.post("/trips", json=payload)
        cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 400

    @pytest.mark.writes
    def test_create_unknown_vehicle(self, api, cleanup):
        response = api.post("/trips", json={"vehicle_id": MISSING_ID, "start_ts": START_TS, "end_ts": END_TS})
        cleanup.track(response, "/trips", "trip_id")
        assert response.status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/trips", content).status_code == 400

    @pytest.mark.writes
    def test_update_partial_changes_only_supplied_fields(self, api, make_trip):
        trip = make_trip(start_geom=START_GEOM, end_geom=END_GEOM, distance_km=6.7)
        changes = {"end_ts": "2026-03-14T08:50:00Z", "distance_km": 7.1}
        response = api.put(f"/trips/{trip['trip_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert_trip(response.json())
        assert response.json() == {**trip, **changes}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_vehicle, make_trip):
        other_vehicle = make_vehicle()
        trip = make_trip()
        changes = {
            "vehicle_id": other_vehicle["vehicle_id"],
            "start_ts": "2026-03-15T08:00:00Z",
            "end_ts": "2026-03-15T09:00:00Z",
            "start_geom": START_GEOM,
            "end_geom": END_GEOM,
            "distance_km": 12.5,
        }
        response = api.put(f"/trips/{trip['trip_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert response.json() == {**trip, **changes}

    @pytest.mark.writes
    def test_update_clears_optional_geometry(self, api, make_trip):
        trip = make_trip(start_geom=START_GEOM)
        response = api.put(f"/trips/{trip['trip_id']}", json={"start_geom": None})
        assert response.status_code == 200, response.text
        assert response.json() == {**trip, "start_geom": None}

    @pytest.mark.writes
    @pytest.mark.parametrize(
        "changes",
        [
            {"start_ts": "2026-03-14T09:00:00Z"},
            {"end_ts": "2026-03-14T07:00:00Z"},
            {"end_ts": START_TS},
            {"distance_km": -1},
            {"start_geom": BAD_POINTS[0]},
            {"end_geom": BAD_POINTS[1]},
            {"vehicle_id": None},
            {"start_ts": None},
            {"end_ts": None},
        ],
    )
    def test_update_rejects_invalid_field(self, api, make_trip, changes):
        trip = make_trip()
        assert api.put(f"/trips/{trip['trip_id']}", json=changes).status_code == 422
        assert api.get(f"/trips/{trip['trip_id']}").json() == trip

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_trip):
        trip = make_trip()
        assert api.put(f"/trips/{trip['trip_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_trip, content):
        trip = make_trip()
        assert send_raw(api, "PUT", f"/trips/{trip['trip_id']}", content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_trip(self, api):
        assert api.put(f"/trips/{MISSING_ID}", json={"distance_km": 1.0}).status_code == 404

    @pytest.mark.writes
    def test_update_unknown_vehicle(self, api, make_trip):
        trip = make_trip()
        assert api.put(f"/trips/{trip['trip_id']}", json={"vehicle_id": MISSING_ID}).status_code == 404

    @pytest.mark.writes
    def test_delete_trip(self, api, make_trip):
        trip = make_trip()
        response = api.delete(f"/trips/{trip['trip_id']}")
        assert response.status_code == 200
        assert response.json() == {"message": "Trip deleted successfully.", "trip_id": trip["trip_id"]}
        assert api.get(f"/trips/{trip['trip_id']}").status_code == 404

    @pytest.mark.writes
    def test_delete_missing_trip(self, api):
        assert api.delete(f"/trips/{MISSING_ID}").status_code == 404


class TestVehicleTrips:
    @pytest.fixture(autouse=True)
    def vehicle_trips_built(self, require_route, existing_vehicle):
        require_route(f"/vehicles/{existing_vehicle['vehicle_id']}/trips")

    def test_vehicle_trips(self, api, existing_trip):
        vehicle_id = existing_trip["vehicle_id"]
        response = api.get(f"/vehicles/{vehicle_id}/trips", params={"limit": 5, "offset": 0})
        body = assert_page(response, 5, 0, BY_VEHICLE_FIELDS)
        assert body["vehicle_id"] == vehicle_id
        assert body["count"] >= 1
        for item in body["items"]:
            assert set(item) == VEHICLE_TRIP_FIELDS
            assert_utc(item["start_ts"])
            assert_utc(item["end_ts"])

    def test_vehicle_trips_count_is_total_before_pagination(self, api, existing_trip):
        assert_count_is_total(api, f"/vehicles/{existing_trip['vehicle_id']}/trips")

    def test_vehicle_trips_missing_vehicle(self, api):
        assert api.get(f"/vehicles/{MISSING_ID}/trips").status_code == 404

    @pytest.mark.parametrize("params", INVALID_TIME_QUERIES)
    def test_vehicle_trips_rejects_invalid_query(self, api, existing_trip, params):
        assert api.get(f"/vehicles/{existing_trip['vehicle_id']}/trips", params=params).status_code == 400

    @pytest.mark.writes
    def test_vehicle_without_trips_returns_empty_page(self, api, make_vehicle):
        vehicle = make_vehicle()
        response = api.get(f"/vehicles/{vehicle['vehicle_id']}/trips")
        assert response.status_code == 200
        body = response.json()
        assert body["vehicle_id"] == vehicle["vehicle_id"]
        assert body["items"] == []
        assert body["count"] == 0

    @pytest.mark.writes
    def test_vehicle_trips_time_range_and_pagination(self, api, make_vehicle, make_trip):
        vehicle_id = make_vehicle()["vehicle_id"]
        morning = make_trip(vehicle_id=vehicle_id, distance_km=6.7)
        make_trip(vehicle_id=vehicle_id, start_ts="2026-03-14T12:00:00Z", end_ts="2026-03-14T12:30:00Z")
        path = f"/vehicles/{vehicle_id}/trips"
        window = api.get(path, params={"from_ts": "2026-03-14T07:00:00Z", "to_ts": "2026-03-14T09:00:00Z"}).json()
        assert window["count"] == 1
        assert window["items"] == [pick(morning, VEHICLE_TRIP_FIELDS)]
        first_page = api.get(path, params={"limit": 1}).json()
        assert len(first_page["items"]) == 1
        assert first_page["count"] == 2
