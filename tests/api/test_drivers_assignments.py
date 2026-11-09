import pytest

from support import (
    MALFORMED_BODIES,
    MISSING_ID,
    assert_count_is_total,
    assert_page,
    assert_utc,
    first_item,
    send_raw,
    unique,
)

DRIVER_FIELDS = {"driver_id", "first_name", "last_name", "license_number", "hired_at"}
ASSIGNMENT_FIELDS = {"assignment_id", "vehicle_id", "driver_id", "assigned_from", "assigned_to"}
DRIVER_TEXT_FIELDS = ["first_name", "last_name", "license_number"]
HIRED_AT = "2024-08-19T09:00:00Z"
ASSIGNED_FROM = "2026-03-01T08:00:00Z"
ASSIGNED_TO = "2026-03-14T17:00:00Z"


@pytest.fixture(scope="module")
def existing_driver(api, require_route):
    return first_item(api, require_route, "/drivers")


@pytest.fixture(scope="module")
def existing_assignment(api, require_route):
    return first_item(api, require_route, "/vehicle-assignments")


def driver_payload(**fields):
    return {
        "first_name": "Elena",
        "last_name": "Rivera",
        "license_number": unique("PR-DRV"),
        "hired_at": HIRED_AT,
        **fields,
    }


@pytest.fixture
def make_driver(api, require_route, cleanup):
    require_route("/drivers")

    def create(**fields):
        response = api.post("/drivers", json=driver_payload(**fields))
        body = cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 201, response.text
        return body

    return create


@pytest.fixture
def make_assignment(api, require_route, cleanup, make_vehicle, make_driver):
    require_route("/vehicle-assignments")

    def create(**fields):
        payload = {"assigned_from": ASSIGNED_FROM, "assigned_to": None, **fields}
        if "vehicle_id" not in payload:
            payload["vehicle_id"] = make_vehicle()["vehicle_id"]
        if "driver_id" not in payload:
            payload["driver_id"] = make_driver()["driver_id"]
        response = api.post("/vehicle-assignments", json=payload)
        body = cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 201, response.text
        return body

    return create


def assert_driver(body):
    assert set(body) == DRIVER_FIELDS
    assert isinstance(body["driver_id"], int) and body["driver_id"] > 0
    assert_utc(body["hired_at"])


def assert_assignment(body):
    assert set(body) == ASSIGNMENT_FIELDS
    assert isinstance(body["assignment_id"], int) and body["assignment_id"] > 0
    assert_utc(body["assigned_from"])
    if body["assigned_to"] is not None:
        assert_utc(body["assigned_to"])


class TestDrivers:
    @pytest.fixture(autouse=True)
    def drivers_built(self, require_route):
        require_route("/drivers")

    def test_list_drivers(self, api):
        body = assert_page(api.get("/drivers", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert_driver(item)

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/drivers")

    @pytest.mark.parametrize("params", [{"limit": -1}, {"offset": -1}, {"limit": "abc"}])
    def test_list_rejects_invalid_pagination(self, api, params):
        assert api.get("/drivers", params=params).status_code == 400

    def test_list_filters_by_name_case_insensitive(self, api, existing_driver):
        fragment = existing_driver["first_name"][:3].upper()
        body = api.get("/drivers", params={"name": fragment, "limit": 1000}).json()
        assert body["count"] >= 1
        assert all(
            fragment.lower() in (item["first_name"] + " " + item["last_name"]).lower()
            for item in body["items"]
        )

    def test_list_filters_by_license_case_insensitive(self, api, existing_driver):
        fragment = existing_driver["license_number"][:4].lower()
        body = api.get("/drivers", params={"license_number": fragment, "limit": 1000}).json()
        assert body["count"] >= 1
        assert all(fragment in item["license_number"].lower() for item in body["items"])

    def test_get_driver(self, api, existing_driver):
        response = api.get(f"/drivers/{existing_driver['driver_id']}")
        assert response.status_code == 200
        assert_driver(response.json())
        assert response.json() == existing_driver

    def test_get_missing_driver(self, api):
        assert api.get(f"/drivers/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_create_driver(self, api, cleanup):
        payload = driver_payload()
        response = api.post("/drivers", json=payload)
        body = cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 201, response.text
        assert_driver(body)
        assert body == {**payload, "driver_id": body["driver_id"]}
        assert api.get(f"/drivers/{body['driver_id']}").json() == body

    @pytest.mark.writes
    def test_create_trims_text_fields(self, make_driver):
        license_number = unique("PR-DRV")
        body = make_driver(first_name="  Elena ", last_name=" Rivera  ", license_number=f" {license_number} ")
        assert body["first_name"] == "Elena"
        assert body["last_name"] == "Rivera"
        assert body["license_number"] == license_number

    @pytest.mark.writes
    def test_create_normalizes_offset_timestamp(self, make_driver):
        assert make_driver(hired_at="2024-08-19T05:00:00-04:00")["hired_at"] == HIRED_AT

    @pytest.mark.writes
    @pytest.mark.parametrize("field", DRIVER_TEXT_FIELDS + ["hired_at"])
    def test_create_requires_field(self, api, cleanup, field):
        payload = driver_payload()
        del payload[field]
        response = api.post("/drivers", json=payload)
        cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code in (400, 422)

    @pytest.mark.writes
    @pytest.mark.parametrize("field", DRIVER_TEXT_FIELDS + ["hired_at"])
    def test_create_rejects_null_field(self, api, cleanup, field):
        response = api.post("/drivers", json=driver_payload(**{field: None}))
        cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 422

    @pytest.mark.writes
    @pytest.mark.parametrize("field", DRIVER_TEXT_FIELDS)
    def test_create_rejects_blank_text(self, api, cleanup, field):
        response = api.post("/drivers", json=driver_payload(**{field: "   "}))
        cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 422

    @pytest.mark.writes
    @pytest.mark.parametrize("hired_at", ["yesterday", "2026-13-01T00:00:00Z"])
    def test_create_rejects_invalid_hired_at(self, api, cleanup, hired_at):
        response = api.post("/drivers", json=driver_payload(hired_at=hired_at))
        cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 422

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/drivers", content).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("padding", ["", "  "])
    def test_create_duplicate_license(self, api, make_driver, cleanup, padding):
        existing = make_driver()
        duplicate = f"{padding}{existing['license_number']}{padding}"
        response = api.post("/drivers", json=driver_payload(license_number=duplicate))
        cleanup.track(response, "/drivers", "driver_id")
        assert response.status_code == 409

    @pytest.mark.writes
    def test_update_partial_changes_only_supplied_fields(self, api, make_driver):
        driver = make_driver()
        response = api.put(f"/drivers/{driver['driver_id']}", json={"last_name": "Santiago"})
        assert response.status_code == 200, response.text
        assert_driver(response.json())
        assert response.json() == {**driver, "last_name": "Santiago"}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_driver):
        driver = make_driver()
        changes = driver_payload(first_name="Ana", last_name="Torres", hired_at="2025-01-02T03:04:05Z")
        response = api.put(f"/drivers/{driver['driver_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert response.json() == {**driver, **changes}

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_driver):
        driver = make_driver()
        assert api.put(f"/drivers/{driver['driver_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_driver, content):
        driver = make_driver()
        assert send_raw(api, "PUT", f"/drivers/{driver['driver_id']}", content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_driver(self, api):
        assert api.put(f"/drivers/{MISSING_ID}", json={"last_name": "Santiago"}).status_code == 404

    @pytest.mark.writes
    def test_update_duplicate_license(self, api, make_driver):
        first = make_driver()
        second = make_driver()
        response = api.put(f"/drivers/{second['driver_id']}", json={"license_number": first["license_number"]})
        assert response.status_code == 409
        assert api.get(f"/drivers/{second['driver_id']}").json() == second

    @pytest.mark.writes
    @pytest.mark.parametrize("field", DRIVER_TEXT_FIELDS + ["hired_at"])
    def test_update_rejects_null_field(self, api, make_driver, field):
        driver = make_driver()
        assert api.put(f"/drivers/{driver['driver_id']}", json={field: None}).status_code == 422
        assert api.get(f"/drivers/{driver['driver_id']}").json() == driver

    @pytest.mark.writes
    @pytest.mark.parametrize("field", DRIVER_TEXT_FIELDS)
    def test_update_rejects_blank_text(self, api, make_driver, field):
        driver = make_driver()
        assert api.put(f"/drivers/{driver['driver_id']}", json={field: "  "}).status_code == 422

    @pytest.mark.writes
    def test_update_rejects_invalid_hired_at(self, api, make_driver):
        driver = make_driver()
        assert api.put(f"/drivers/{driver['driver_id']}", json={"hired_at": "yesterday"}).status_code == 422

    @pytest.mark.writes
    def test_delete_driver(self, api, make_driver):
        driver = make_driver()
        response = api.delete(f"/drivers/{driver['driver_id']}")
        assert response.status_code == 200
        assert response.json() == {"message": "Driver deleted successfully.", "driver_id": driver["driver_id"]}
        assert api.get(f"/drivers/{driver['driver_id']}").status_code == 404

    @pytest.mark.writes
    def test_delete_missing_driver(self, api):
        assert api.delete(f"/drivers/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_delete_referenced_driver_returns_409(self, api, make_assignment):
        assignment = make_assignment()
        assert api.delete(f"/drivers/{assignment['driver_id']}").status_code == 409
        assert api.get(f"/drivers/{assignment['driver_id']}").status_code == 200


class TestVehicleAssignments:
    @pytest.fixture(autouse=True)
    def assignments_built(self, require_route):
        require_route("/vehicle-assignments")

    def test_list_assignments(self, api):
        body = assert_page(api.get("/vehicle-assignments", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert_assignment(item)

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/vehicle-assignments")

    @pytest.mark.parametrize(
        "params",
        [
            {"limit": -1},
            {"offset": -1},
            {"vehicle_id": 0},
            {"vehicle_id": "abc"},
            {"driver_id": -1},
            {"active": "maybe"},
        ],
    )
    def test_list_rejects_invalid_query(self, api, params):
        assert api.get("/vehicle-assignments", params=params).status_code == 400

    def test_list_active_filter_splits_rows(self, api):
        total = api.get("/vehicle-assignments", params={"limit": 1}).json()["count"]
        active = api.get("/vehicle-assignments", params={"active": "true", "limit": 1000}).json()
        closed = api.get("/vehicle-assignments", params={"active": "false", "limit": 1000}).json()
        assert all(item["assigned_to"] is None for item in active["items"])
        assert all(item["assigned_to"] is not None for item in closed["items"])
        assert active["count"] + closed["count"] == total

    def test_list_filters_by_vehicle_and_driver(self, api, existing_assignment):
        params = {
            "vehicle_id": existing_assignment["vehicle_id"],
            "driver_id": existing_assignment["driver_id"],
            "limit": 1000,
        }
        body = api.get("/vehicle-assignments", params=params).json()
        assert existing_assignment in body["items"]
        assert all(
            item["vehicle_id"] == params["vehicle_id"] and item["driver_id"] == params["driver_id"]
            for item in body["items"]
        )

    def test_get_assignment(self, api, existing_assignment):
        response = api.get(f"/vehicle-assignments/{existing_assignment['assignment_id']}")
        assert response.status_code == 200
        assert_assignment(response.json())
        assert response.json() == existing_assignment

    def test_get_missing_assignment(self, api):
        assert api.get(f"/vehicle-assignments/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_create_assignment(self, api, cleanup, make_vehicle, make_driver):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": ASSIGNED_FROM,
            "assigned_to": None,
        }
        response = api.post("/vehicle-assignments", json=payload)
        body = cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 201, response.text
        assert_assignment(body)
        assert body == {**payload, "assignment_id": body["assignment_id"]}

    @pytest.mark.writes
    def test_create_closed_assignment(self, make_assignment):
        assert make_assignment(assigned_to=ASSIGNED_TO)["assigned_to"] == ASSIGNED_TO

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "driver_id", "assigned_from"])
    def test_create_requires_field(self, api, cleanup, make_vehicle, make_driver, field):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": ASSIGNED_FROM,
        }
        del payload[field]
        response = api.post("/vehicle-assignments", json=payload)
        cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "driver_id"])
    @pytest.mark.parametrize("value", [0, -1, "abc"])
    def test_create_rejects_invalid_reference_id(self, api, cleanup, make_vehicle, make_driver, field, value):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": ASSIGNED_FROM,
            field: value,
        }
        response = api.post("/vehicle-assignments", json=payload)
        cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "driver_id"])
    def test_create_unknown_reference(self, api, cleanup, make_vehicle, make_driver, field):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": ASSIGNED_FROM,
            field: MISSING_ID,
        }
        response = api.post("/vehicle-assignments", json=payload)
        cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize("assigned_to", [ASSIGNED_FROM, "2026-02-28T08:00:00Z"])
    def test_create_rejects_invalid_interval(self, api, cleanup, make_vehicle, make_driver, assigned_to):
        payload = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": ASSIGNED_FROM,
            "assigned_to": assigned_to,
        }
        response = api.post("/vehicle-assignments", json=payload)
        cleanup.track(response, "/vehicle-assignments", "assignment_id")
        assert response.status_code == 422

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/vehicle-assignments", content).status_code == 400

    @pytest.mark.writes
    def test_list_filters_combine_with_and(self, api, make_assignment):
        assignment = make_assignment()
        base = {"vehicle_id": assignment["vehicle_id"], "driver_id": assignment["driver_id"]}
        active = api.get("/vehicle-assignments", params={**base, "active": "true"}).json()
        closed = api.get("/vehicle-assignments", params={**base, "active": "false"}).json()
        assert active["count"] == 1
        assert active["items"] == [assignment]
        assert closed["count"] == 0
        assert closed["items"] == []

    @pytest.mark.writes
    def test_update_closes_active_assignment(self, api, make_assignment):
        assignment = make_assignment()
        response = api.put(
            f"/vehicle-assignments/{assignment['assignment_id']}", json={"assigned_to": ASSIGNED_TO}
        )
        assert response.status_code == 200, response.text
        assert_assignment(response.json())
        assert response.json() == {**assignment, "assigned_to": ASSIGNED_TO}

    @pytest.mark.writes
    def test_update_reopens_assignment(self, api, make_assignment):
        assignment = make_assignment(assigned_to=ASSIGNED_TO)
        response = api.put(f"/vehicle-assignments/{assignment['assignment_id']}", json={"assigned_to": None})
        assert response.status_code == 200, response.text
        assert response.json() == {**assignment, "assigned_to": None}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_assignment, make_vehicle, make_driver):
        changes = {
            "vehicle_id": make_vehicle()["vehicle_id"],
            "driver_id": make_driver()["driver_id"],
            "assigned_from": "2026-04-01T08:00:00Z",
            "assigned_to": "2026-04-02T08:00:00Z",
        }
        assignment = make_assignment()
        response = api.put(f"/vehicle-assignments/{assignment['assignment_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert response.json() == {**assignment, **changes}

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_assignment):
        assignment = make_assignment()
        assert api.put(f"/vehicle-assignments/{assignment['assignment_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_assignment, content):
        assignment = make_assignment()
        path = f"/vehicle-assignments/{assignment['assignment_id']}"
        assert send_raw(api, "PUT", path, content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_assignment(self, api):
        assert api.put(f"/vehicle-assignments/{MISSING_ID}", json={"assigned_to": ASSIGNED_TO}).status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["vehicle_id", "driver_id"])
    def test_update_unknown_reference(self, api, make_assignment, field):
        assignment = make_assignment()
        response = api.put(f"/vehicle-assignments/{assignment['assignment_id']}", json={field: MISSING_ID})
        assert response.status_code == 404

    @pytest.mark.writes
    def test_update_rejects_invalid_interval(self, api, make_assignment):
        assignment = make_assignment(assigned_to=ASSIGNED_TO)
        path = f"/vehicle-assignments/{assignment['assignment_id']}"
        assert api.put(path, json={"assigned_from": "2026-03-20T08:00:00Z"}).status_code == 422
        assert api.get(path).json() == assignment

    @pytest.mark.writes
    def test_decision_assignment_null_on_put(self, api, make_assignment):
        assignment = make_assignment()
        path = f"/vehicle-assignments/{assignment['assignment_id']}"
        assert api.put(path, json={"vehicle_id": None}).status_code == 400
        assert api.put(path, json={"driver_id": None}).status_code == 400
        assert api.put(path, json={"assigned_from": None}).status_code == 422
        assert api.get(path).json() == assignment

    @pytest.mark.writes
    def test_delete_assignment(self, api, make_assignment):
        assignment = make_assignment()
        response = api.delete(f"/vehicle-assignments/{assignment['assignment_id']}")
        assert response.status_code == 200
        assert response.json() == {
            "message": "Vehicle assignment deleted successfully.",
            "assignment_id": assignment["assignment_id"],
        }
        assert api.get(f"/vehicle-assignments/{assignment['assignment_id']}").status_code == 404

    @pytest.mark.writes
    def test_delete_missing_assignment(self, api):
        assert api.delete(f"/vehicle-assignments/{MISSING_ID}").status_code == 404
