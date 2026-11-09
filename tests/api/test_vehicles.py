import pytest

from support import MALFORMED_BODIES, MISSING_ID, PAGE_FIELDS, assert_utc, send_raw, unique

VEHICLE_FIELDS = {
    "vehicle_id", "vehicle_type_id", "vehicle_status_id",
    "plate_number", "make", "model", "year", "created_at",
}
LOCATION_FIELDS = {
    "vehicle_id", "plate_number", "status", "vehicle_kind", "fuel_type",
    "emissions_rating", "last_ts", "last_geom", "speed_kph", "heading_deg",
}
PING_GEOM = {"type": "Point", "coordinates": [-67.1453, 18.2011]}


@pytest.fixture(scope="module", autouse=True)
def vehicles_built(require_route):
    require_route("/vehicles")


@pytest.fixture(scope="module")
def located_vehicle(api):
    for vehicle in api.get("/vehicles", params={"limit": 50}).json()["items"]:
        if api.get(f"/vehicles/{vehicle['vehicle_id']}/current-location").status_code == 200:
            return vehicle
    pytest.skip("No vehicle with pings in the first 50 vehicles")


def assert_vehicle(body):
    assert set(body) == VEHICLE_FIELDS
    assert isinstance(body["vehicle_id"], int) and body["vehicle_id"] > 0
    assert_utc(body["created_at"])


def list_all(api, **params):
    return api.get("/vehicles", params={"limit": 100_000, **params}).json()


def test_list_vehicles(api):
    response = api.get("/vehicles", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == PAGE_FIELDS
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert len(body["items"]) <= 5
    for item in body["items"]:
        assert_vehicle(item)


def test_list_count_is_total_before_pagination(api):
    first = api.get("/vehicles", params={"limit": 1}).json()
    everything = list_all(api)
    assert len(first["items"]) == min(1, everything["count"])
    assert first["count"] == everything["count"] == len(everything["items"])


def test_list_offset_skips_rows(api):
    page = api.get("/vehicles", params={"limit": 2, "offset": 0}).json()["items"]
    if len(page) < 2:
        pytest.skip("Need at least two vehicles")
    shifted = api.get("/vehicles", params={"limit": 1, "offset": 1}).json()
    assert shifted["offset"] == 1
    assert shifted["items"] == page[1:]


def test_decision_limit_zero(api):
    response = api.get("/vehicles", params={"limit": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["limit"] == 0
    assert body["count"] == list_all(api)["count"]


@pytest.mark.parametrize("params", [{"limit": -1}, {"offset": -1}, {"limit": "abc"}, {"offset": "1.5"}])
def test_list_rejects_invalid_pagination(api, params):
    assert api.get("/vehicles", params=params).status_code == 400


def test_list_filters_by_partial_plate(api, existing_vehicle):
    fragment = existing_vehicle["plate_number"][1:4]
    body = list_all(api, plate_number=fragment)
    assert body["count"] >= 1
    assert all(fragment in item["plate_number"] for item in body["items"])


def test_list_filters_by_status_id(api, existing_vehicle):
    status_id = existing_vehicle["vehicle_status_id"]
    body = list_all(api, status=status_id)
    assert body["count"] >= 1
    assert all(item["vehicle_status_id"] == status_id for item in body["items"])


def test_list_status_name_matches_status_id(api, located_vehicle):
    status_name = api.get(f"/vehicles/{located_vehicle['vehicle_id']}/current-location").json()["status"]
    by_name = list_all(api, status=status_name)
    by_id = list_all(api, status=located_vehicle["vehicle_status_id"])
    assert by_name["count"] == by_id["count"] >= 1
    assert by_name["items"] == by_id["items"]


def test_list_combines_filters(api, existing_vehicle):
    body = list_all(
        api,
        plate_number=existing_vehicle["plate_number"],
        status=existing_vehicle["vehicle_status_id"],
    )
    assert existing_vehicle in body["items"]
    assert all(
        item["vehicle_status_id"] == existing_vehicle["vehicle_status_id"]
        and existing_vehicle["plate_number"] in item["plate_number"]
        for item in body["items"]
    )


def test_get_vehicle(api, existing_vehicle):
    response = api.get(f"/vehicles/{existing_vehicle['vehicle_id']}")
    assert response.status_code == 200
    body = response.json()
    assert_vehicle(body)
    assert body == existing_vehicle


def test_get_missing_vehicle(api):
    assert api.get(f"/vehicles/{MISSING_ID}").status_code == 404


def test_decision_nonpositive_path_ids(api):
    assert api.get("/vehicles/0").status_code == 404
    assert api.get("/vehicles/-1").status_code == 404


def test_current_location(api, located_vehicle):
    response = api.get(f"/vehicles/{located_vehicle['vehicle_id']}/current-location")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == LOCATION_FIELDS
    assert body["vehicle_id"] == located_vehicle["vehicle_id"]
    assert body["plate_number"] == located_vehicle["plate_number"]
    assert_utc(body["last_ts"])
    assert body["last_geom"]["type"] == "Point"
    lon, lat = body["last_geom"]["coordinates"]
    assert -180 <= lon <= 180
    assert -90 <= lat <= 90


@pytest.mark.parametrize("vehicle_id", ["0", "-5", "abc"])
def test_current_location_rejects_invalid_id(api, vehicle_id):
    assert api.get(f"/vehicles/{vehicle_id}/current-location").status_code == 400


def test_current_location_missing_vehicle(api):
    assert api.get(f"/vehicles/{MISSING_ID}/current-location").status_code == 404


@pytest.mark.writes
def test_create_vehicle(api, vehicle_refs, cleanup):
    payload = {**vehicle_refs, "plate_number": unique("T"), "make": "Toyota", "model": "Hilux", "year": 2024}
    response = api.post("/vehicles", json=payload)
    body = cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 201, response.text
    assert_vehicle(body)
    assert {field: body[field] for field in payload} == payload
    assert api.get(f"/vehicles/{body['vehicle_id']}").json() == body


@pytest.mark.writes
def test_create_vehicle_with_required_fields_only(make_vehicle):
    body = make_vehicle()
    assert_vehicle(body)
    assert body["make"] is None
    assert body["model"] is None
    assert body["year"] is None


@pytest.mark.writes
def test_create_trims_make_and_model(make_vehicle):
    body = make_vehicle(make="  Toyota ", model=" Hilux  ")
    assert body["make"] == "Toyota"
    assert body["model"] == "Hilux"


@pytest.mark.writes
@pytest.mark.parametrize("year", [1950, 2100])
def test_create_accepts_year_bounds(make_vehicle, year):
    assert make_vehicle(year=year)["year"] == year


@pytest.mark.writes
@pytest.mark.parametrize("year", [1949, 2101])
def test_create_rejects_year_out_of_range(api, vehicle_refs, cleanup, year):
    response = api.post("/vehicles", json={**vehicle_refs, "plate_number": unique("T"), "year": year})
    cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("field", ["vehicle_type_id", "vehicle_status_id", "plate_number"])
def test_create_requires_field(api, vehicle_refs, cleanup, field):
    payload = {**vehicle_refs, "plate_number": unique("T")}
    del payload[field]
    response = api.post("/vehicles", json=payload)
    cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("plate", ["", "   "])
def test_create_rejects_empty_plate(api, vehicle_refs, cleanup, plate):
    response = api.post("/vehicles", json={**vehicle_refs, "plate_number": plate})
    cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("content", MALFORMED_BODIES)
def test_create_rejects_malformed_json(api, content):
    assert send_raw(api, "POST", "/vehicles", content).status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("field", ["vehicle_type_id", "vehicle_status_id"])
def test_create_unknown_reference(api, vehicle_refs, cleanup, field):
    payload = {**vehicle_refs, "plate_number": unique("T"), field: MISSING_ID}
    response = api.post("/vehicles", json=payload)
    cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 404


@pytest.mark.writes
def test_create_duplicate_plate(api, make_vehicle, vehicle_refs, cleanup):
    existing = make_vehicle()
    response = api.post("/vehicles", json={**vehicle_refs, "plate_number": existing["plate_number"]})
    cleanup.track(response, "/vehicles", "vehicle_id")
    assert response.status_code == 409


@pytest.mark.writes
def test_list_filter_returns_created_vehicle(api, make_vehicle):
    vehicle = make_vehicle(make="Toyota", model="Hilux", year=2024)
    response = api.get("/vehicles", params={"plate_number": vehicle["plate_number"]})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"] == [vehicle]


@pytest.mark.writes
def test_update_partial_changes_only_supplied_fields(api, make_vehicle):
    vehicle = make_vehicle(make="Toyota", model="Hilux", year=2024)
    response = api.put(f"/vehicles/{vehicle['vehicle_id']}", json={"model": "Tacoma"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert_vehicle(body)
    assert body == {**vehicle, "model": "Tacoma"}


@pytest.mark.writes
def test_update_all_fields(api, make_vehicle, vehicle_refs):
    vehicle = make_vehicle()
    changes = {**vehicle_refs, "plate_number": unique("T"), "make": "Ford", "model": "Ranger", "year": 2025}
    response = api.put(f"/vehicles/{vehicle['vehicle_id']}", json=changes)
    assert response.status_code == 200, response.text
    assert response.json() == {**vehicle, **changes}


@pytest.mark.writes
def test_update_rejects_empty_payload(api, make_vehicle):
    vehicle = make_vehicle()
    assert api.put(f"/vehicles/{vehicle['vehicle_id']}", json={}).status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("content", MALFORMED_BODIES)
def test_update_rejects_malformed_json(api, make_vehicle, content):
    vehicle = make_vehicle()
    assert send_raw(api, "PUT", f"/vehicles/{vehicle['vehicle_id']}", content).status_code == 400


@pytest.mark.writes
def test_update_missing_vehicle(api):
    assert api.put(f"/vehicles/{MISSING_ID}", json={"make": "Ford"}).status_code == 404


@pytest.mark.writes
@pytest.mark.parametrize("year", [1949, 2101])
def test_update_rejects_year_out_of_range(api, make_vehicle, year):
    vehicle = make_vehicle()
    assert api.put(f"/vehicles/{vehicle['vehicle_id']}", json={"year": year}).status_code == 400


@pytest.mark.writes
@pytest.mark.parametrize("field", ["vehicle_type_id", "vehicle_status_id"])
def test_update_unknown_reference(api, make_vehicle, field):
    vehicle = make_vehicle()
    assert api.put(f"/vehicles/{vehicle['vehicle_id']}", json={field: MISSING_ID}).status_code == 404


@pytest.mark.writes
def test_update_duplicate_plate(api, make_vehicle):
    first = make_vehicle()
    second = make_vehicle()
    response = api.put(f"/vehicles/{second['vehicle_id']}", json={"plate_number": first["plate_number"]})
    assert response.status_code == 409
    assert api.get(f"/vehicles/{second['vehicle_id']}").json() == second


@pytest.mark.writes
@pytest.mark.parametrize("field", ["vehicle_type_id", "vehicle_status_id", "plate_number"])
def test_update_rejects_null_required_field(api, make_vehicle, field):
    vehicle = make_vehicle()
    response = api.put(f"/vehicles/{vehicle['vehicle_id']}", json={field: None})
    assert response.status_code == 400
    assert api.get(f"/vehicles/{vehicle['vehicle_id']}").json() == vehicle


@pytest.mark.writes
def test_delete_vehicle(api, make_vehicle):
    vehicle = make_vehicle()
    response = api.delete(f"/vehicles/{vehicle['vehicle_id']}")
    assert response.status_code == 200
    assert response.json() == {"message": "Vehicle deleted successfully.", "vehicle_id": vehicle["vehicle_id"]}
    assert api.get(f"/vehicles/{vehicle['vehicle_id']}").status_code == 404


@pytest.mark.writes
def test_delete_missing_vehicle(api):
    assert api.delete(f"/vehicles/{MISSING_ID}").status_code == 404


@pytest.mark.writes
def test_delete_referenced_vehicle_returns_409(api, make_vehicle, cleanup, require_route):
    require_route("/location-pings")
    vehicle = make_vehicle()
    ping = {"vehicle_id": vehicle["vehicle_id"], "ts": "2026-03-14T09:58:20Z", "geom": PING_GEOM}
    response = api.post("/location-pings", json=ping)
    cleanup.track(response, "/location-pings", "ping_id")
    assert response.status_code == 201, response.text
    assert api.delete(f"/vehicles/{vehicle['vehicle_id']}").status_code == 409
    assert api.get(f"/vehicles/{vehicle['vehicle_id']}").status_code == 200


@pytest.mark.writes
def test_current_location_without_pings_returns_204(api, make_vehicle):
    vehicle = make_vehicle()
    response = api.get(f"/vehicles/{vehicle['vehicle_id']}/current-location")
    assert response.status_code == 204
    assert response.content == b""
