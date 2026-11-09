import pytest

from support import (
    INVALID_BBOXES,
    MALFORMED_BODIES,
    MISSING_ID,
    TEST_BBOX,
    VALID_BBOX,
    assert_count_is_total,
    assert_page,
    assert_utc,
    first_item,
    send_raw,
    unique,
)

ROAD_FIELDS = {"road_id", "name", "speed_limit_kph", "is_oneway", "direction", "geom", "created_at"}
ROAD_DETAIL_FIELDS = {"road_id", "name", "speed_limit_kph", "geom", "created_at"}
ROAD_EXTRAS = {"is_oneway", "direction"}
ROAD_ITEM_FIELDS = {"road_id", "name", "speed_limit_kph", "created_at"}
FEATURE_PROPERTIES = {"road_id", "name", "speed_limit_kph", "is_oneway", "direction", "created_at"}
COLLECTION_FIELDS = {"type", "count", "limit", "offset", "features"}
PARKING_FIELDS = {"parking_area_id", "name", "capacity", "geom", "created_at"}
PARKING_ITEM_FIELDS = {"parking_area_id", "name", "capacity", "created_at"}

LINE = {"type": "LineString", "coordinates": [[-67.1601, 18.211], [-67.1588, 18.2101], [-67.1573, 18.2092]]}
OTHER_LINE = {"type": "LineString", "coordinates": [[-67.15, 18.2], [-67.14, 18.21]]}


def square(min_lon, min_lat, max_lon, max_lat):
    ring = [[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]
    return {"type": "Polygon", "coordinates": [ring]}


POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [-67.141, 18.2105], [-67.1402, 18.2105], [-67.1402, 18.2098], [-67.141, 18.2098], [-67.141, 18.2105],
    ]],
}
OTHER_POLYGON = square(-67.15, 18.2, -67.14, 18.21)

ROAD_BBOX_CASES = {
    "inside": [[-9.8, -9.8], [-9.2, -9.2]],
    "crosses": [[-10.5, -9.5], [-8.5, -9.5]],
    "touches": [[-11.0, -9.5], [-10.0, -9.5]],
    "outside": [[-12.0, -12.0], [-11.0, -11.0]],
}
PARKING_BBOX_CASES = {
    "inside": square(-9.8, -9.8, -9.6, -9.6),
    "crosses": square(-10.2, -9.6, -9.8, -9.4),
    "touches": square(-10.4, -9.6, -10.0, -9.4),
    "outside": square(-12.0, -12.0, -11.0, -11.0),
}
BAD_LINES = [
    {"type": "Point", "coordinates": [-67.1, 18.2]},
    POLYGON,
    {"type": "LineString", "coordinates": [[-67.1, 18.2]]},
    {"type": "LineString", "coordinates": [[-200.0, 18.2], [-67.1, 18.3]]},
    {"type": "LineString"},
    "LINESTRING(-67.1 18.2, -67.0 18.3)",
]
BAD_POLYGONS = [
    LINE,
    {"type": "Point", "coordinates": [-67.1, 18.2]},
    {"type": "Polygon", "coordinates": [[[-67.141, 18.2105], [-67.1402, 18.2105], [-67.1402, 18.2098], [-67.141, 18.2098]]]},
    {"type": "Polygon", "coordinates": [[[-67.141, 18.2105], [-67.1402, 18.2105], [-67.141, 18.2105]]]},
    {"type": "Polygon"},
    "POLYGON((0 0, 1 0, 1 1, 0 0))",
]


def assert_line(geom):
    assert geom["type"] == "LineString"
    assert len(geom["coordinates"]) >= 2
    assert all(-180 <= lon <= 180 and -90 <= lat <= 90 for lon, lat in geom["coordinates"])


def road_detail(body):
    return {field: body[field] for field in ROAD_DETAIL_FIELDS}


def assert_road_detail(body):
    assert set(body) - ROAD_EXTRAS == ROAD_DETAIL_FIELDS
    assert_line(body["geom"])
    assert_utc(body["created_at"])


def assert_parking(body):
    assert set(body) == PARKING_FIELDS
    assert body["geom"]["type"] == "Polygon"
    assert_utc(body["created_at"])


def media_type(response):
    return response.headers.get("content-type", "").split(";")[0].strip()


@pytest.fixture(scope="module")
def existing_road(api, require_route):
    return first_item(api, require_route, "/road-segments")


@pytest.fixture(scope="module")
def existing_parking(api, require_route):
    return first_item(api, require_route, "/parking-areas")


@pytest.fixture
def make_road(api, require_route, cleanup):
    require_route("/road-segments")

    def create(**fields):
        response = api.post("/road-segments", json={"name": unique("Road"), "geom": LINE, **fields})
        body = cleanup.track(response, "/road-segments", "road_id")
        assert response.status_code == 201, response.text
        return body

    return create


@pytest.fixture
def make_parking(api, require_route, cleanup):
    require_route("/parking-areas")

    def create(**fields):
        response = api.post("/parking-areas", json={"name": unique("Lot"), "geom": POLYGON, **fields})
        body = cleanup.track(response, "/parking-areas", "parking_area_id")
        assert response.status_code == 201, response.text
        return body

    return create


class TestRoadSegments:
    @pytest.fixture(autouse=True)
    def roads_built(self, require_route):
        require_route("/road-segments")

    def test_list_road_segments(self, api):
        body = assert_page(api.get("/road-segments", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert set(item) == ROAD_ITEM_FIELDS
            assert_utc(item["created_at"])

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/road-segments")

    @pytest.mark.parametrize("params", [{"limit": -1}, {"offset": -1}, {"limit": "abc"}])
    def test_list_rejects_invalid_pagination(self, api, params):
        assert api.get("/road-segments", params=params).status_code == 400

    def test_list_filters_by_name_case_insensitive(self, api, existing_road):
        fragment = existing_road["name"][:3].swapcase()
        body = api.get("/road-segments", params={"name": fragment, "limit": 1000}).json()
        assert body["count"] >= 1
        assert all(fragment.lower() in item["name"].lower() for item in body["items"])

    def test_list_filters_by_speed_range(self, api):
        params = {"min_speed_kph": 40, "max_speed_kph": 80, "limit": 1000}
        body = api.get("/road-segments", params=params).json()
        assert all(40 <= item["speed_limit_kph"] <= 80 for item in body["items"])

    def test_list_filters_by_bbox(self, api):
        everything = api.get("/road-segments", params={"limit": 1}).json()["count"]
        response = api.get("/road-segments", params={"bbox": VALID_BBOX, "limit": 5})
        body = assert_page(response, 5, 0)
        assert 1 <= body["count"] <= everything

    @pytest.mark.parametrize("bbox", INVALID_BBOXES)
    def test_list_rejects_invalid_bbox(self, api, bbox):
        assert api.get("/road-segments", params={"bbox": bbox}).status_code == 400

    def test_get_road_segment(self, api, existing_road):
        response = api.get(f"/road-segments/{existing_road['road_id']}")
        assert response.status_code == 200
        body = response.json()
        assert_road_detail(body)
        assert {field: body[field] for field in ROAD_ITEM_FIELDS} == existing_road

    def test_get_missing_road_segment(self, api):
        assert api.get(f"/road-segments/{MISSING_ID}").status_code == 404

    def test_decision_road_segment_extra_keys(self, api, existing_road):
        body = api.get(f"/road-segments/{existing_road['road_id']}").json()
        assert set(body) == ROAD_DETAIL_FIELDS | ROAD_EXTRAS

    @pytest.mark.writes
    def test_create_road_segment(self, api, cleanup):
        payload = {
            "name": unique("Road"),
            "speed_limit_kph": 60,
            "is_oneway": True,
            "direction": "forward",
            "geom": LINE,
        }
        response = api.post("/road-segments", json=payload)
        body = cleanup.track(response, "/road-segments", "road_id")
        assert response.status_code == 201, response.text
        assert set(body) == ROAD_FIELDS
        assert_utc(body["created_at"])
        assert body == {**payload, "road_id": body["road_id"], "created_at": body["created_at"]}
        assert road_detail(api.get(f"/road-segments/{body['road_id']}").json()) == road_detail(body)

    @pytest.mark.writes
    def test_create_with_required_fields_only(self, make_road):
        body = make_road()
        assert body["speed_limit_kph"] is None
        assert body["geom"] == LINE

    @pytest.mark.writes
    @pytest.mark.parametrize("direction", ["both", "forward"])
    def test_create_accepts_direction(self, make_road, direction):
        assert make_road(direction=direction)["direction"] == direction

    @pytest.mark.writes
    def test_create_accepts_zero_speed(self, make_road):
        assert make_road(speed_limit_kph=0)["speed_limit_kph"] == 0

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["name", "geom"])
    def test_create_requires_field(self, api, cleanup, field):
        payload = {"name": unique("Road"), "geom": LINE}
        del payload[field]
        response = api.post("/road-segments", json=payload)
        cleanup.track(response, "/road-segments", "road_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("changes", [{"name": "   "}, {"speed_limit_kph": -1}, {"direction": "backward"}])
    def test_create_rejects_invalid_field(self, api, cleanup, changes):
        response = api.post("/road-segments", json={"name": unique("Road"), "geom": LINE, **changes})
        cleanup.track(response, "/road-segments", "road_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("geom", BAD_LINES)
    def test_create_rejects_bad_geometry(self, api, cleanup, geom):
        response = api.post("/road-segments", json={"name": unique("Road"), "geom": geom})
        cleanup.track(response, "/road-segments", "road_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/road-segments", content).status_code == 400

    @pytest.mark.writes
    def test_list_bbox_returns_inside_touching_and_crossing(self, api, make_road):
        tag = unique("BBOX")
        for case, coordinates in ROAD_BBOX_CASES.items():
            make_road(name=f"{tag} {case}", geom={"type": "LineString", "coordinates": coordinates})
        body = api.get("/road-segments", params={"bbox": TEST_BBOX, "name": tag, "limit": 100}).json()
        assert {item["name"] for item in body["items"]} == {f"{tag} inside", f"{tag} crosses", f"{tag} touches"}
        assert body["count"] == 3

    @pytest.mark.writes
    def test_list_filter_returns_created_road(self, api, make_road):
        road = make_road(speed_limit_kph=60)
        body = api.get("/road-segments", params={"name": road["name"].lower()}).json()
        assert body["count"] == 1
        assert body["items"] == [{field: road[field] for field in ROAD_ITEM_FIELDS}]

    @pytest.mark.writes
    def test_update_partial_changes_only_supplied_fields(self, api, make_road):
        road = make_road(speed_limit_kph=60, is_oneway=True, direction="forward")
        response = api.put(f"/road-segments/{road['road_id']}", json={"speed_limit_kph": 80})
        assert response.status_code == 200, response.text
        assert_road_detail(response.json())
        assert road_detail(response.json()) == {**road_detail(road), "speed_limit_kph": 80}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_road):
        road = make_road()
        changes = {
            "name": unique("Road"),
            "speed_limit_kph": 45,
            "is_oneway": False,
            "direction": "both",
            "geom": OTHER_LINE,
        }
        response = api.put(f"/road-segments/{road['road_id']}", json=changes)
        assert response.status_code == 200, response.text
        expected = {**road, **changes}
        assert road_detail(response.json()) == road_detail(expected)

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_road):
        road = make_road()
        assert api.put(f"/road-segments/{road['road_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_road, content):
        road = make_road()
        assert send_raw(api, "PUT", f"/road-segments/{road['road_id']}", content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_road_segment(self, api):
        assert api.put(f"/road-segments/{MISSING_ID}", json={"speed_limit_kph": 80}).status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize(
        "changes",
        [{"speed_limit_kph": -1}, {"name": None}, {"name": "  "}, {"geom": None}, {"geom": BAD_LINES[0]}],
    )
    def test_update_rejects_invalid_field(self, api, make_road, changes):
        road = make_road()
        response = api.put(f"/road-segments/{road['road_id']}", json=changes)
        assert response.status_code == 400
        assert road_detail(api.get(f"/road-segments/{road['road_id']}").json()) == road_detail(road)

    @pytest.mark.writes
    @pytest.mark.parametrize("suffix", ["", "/remove"])
    def test_delete_road_segment(self, api, make_road, suffix):
        road = make_road()
        response = api.delete(f"/road-segments/{road['road_id']}{suffix}")
        assert response.status_code == 200
        assert response.json() == {"message": "Road segment deleted successfully.", "road_id": road["road_id"]}
        assert api.get(f"/road-segments/{road['road_id']}").status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize("suffix", ["", "/remove"])
    def test_delete_missing_road_segment(self, api, suffix):
        assert api.delete(f"/road-segments/{MISSING_ID}{suffix}").status_code == 404


class TestRoadSegmentsGeoJSON:
    @pytest.fixture(autouse=True)
    def geojson_built(self, require_route):
        require_route("/road-segments/geojson")

    def test_geojson(self, api):
        response = api.get("/road-segments/geojson", params={"limit": 5, "offset": 0})
        assert response.status_code == 200
        assert media_type(response) == "application/geo+json"
        body = response.json()
        assert set(body) == COLLECTION_FIELDS
        assert body["type"] == "FeatureCollection"
        assert body["limit"] == 5
        assert body["offset"] == 0
        assert len(body["features"]) <= 5
        for feature in body["features"]:
            assert set(feature) == {"type", "geometry", "properties"}
            assert feature["type"] == "Feature"
            assert_line(feature["geometry"])
            assert set(feature["properties"]) == FEATURE_PROPERTIES
            assert_utc(feature["properties"]["created_at"])

    def test_geojson_count_is_total_before_pagination(self, api):
        one = api.get("/road-segments/geojson", params={"limit": 1}).json()
        two = api.get("/road-segments/geojson", params={"limit": 2}).json()
        if two["count"] < 2:
            pytest.skip("Need at least two road segments")
        assert len(one["features"]) == 1
        assert one["count"] == two["count"]

    def test_geojson_filters_by_name_case_insensitive(self, api):
        sample = api.get("/road-segments/geojson", params={"limit": 1}).json()["features"]
        if not sample:
            pytest.skip("No road segments")
        fragment = sample[0]["properties"]["name"][:3].swapcase()
        body = api.get("/road-segments/geojson", params={"name": fragment, "limit": 1000}).json()
        assert body["count"] >= 1
        assert all(fragment.lower() in feature["properties"]["name"].lower() for feature in body["features"])

    def test_geojson_filters_by_speed_range(self, api):
        params = {"min_speed_kph": 40, "max_speed_kph": 80, "limit": 1000}
        body = api.get("/road-segments/geojson", params=params).json()
        assert all(40 <= feature["properties"]["speed_limit_kph"] <= 80 for feature in body["features"])

    def test_geojson_rejects_min_speed_above_max(self, api):
        params = {"min_speed_kph": 80, "max_speed_kph": 40}
        assert api.get("/road-segments/geojson", params=params).status_code == 400

    @pytest.mark.parametrize(
        "params",
        [{"limit": -1}, {"offset": -1}, {"limit": "abc"}, {"min_speed_kph": "abc"}, {"max_speed_kph": -5}],
    )
    def test_geojson_rejects_invalid_query_types(self, api, params):
        assert api.get("/road-segments/geojson", params=params).status_code == 422

    def test_decision_geojson_bbox(self, api):
        plain = api.get("/road-segments/geojson", params={"limit": 1}).json()
        response = api.get("/road-segments/geojson", params={"limit": 1, "bbox": TEST_BBOX})
        assert response.status_code == 200
        assert response.json()["count"] == plain["count"]

    @pytest.mark.writes
    def test_geojson_returns_created_road(self, api, make_road):
        road = make_road(speed_limit_kph=60, is_oneway=True, direction="forward")
        response = api.get("/road-segments/geojson", params={"name": road["name"]})
        assert response.status_code == 200
        assert media_type(response) == "application/geo+json"
        body = response.json()
        assert body["count"] == 1
        assert body["features"] == [{
            "type": "Feature",
            "geometry": LINE,
            "properties": {field: road[field] for field in FEATURE_PROPERTIES},
        }]


class TestParkingAreas:
    @pytest.fixture(autouse=True)
    def parking_built(self, require_route):
        require_route("/parking-areas")

    def test_list_parking_areas(self, api):
        body = assert_page(api.get("/parking-areas", params={"limit": 5, "offset": 0}), 5, 0)
        for item in body["items"]:
            assert set(item) == PARKING_ITEM_FIELDS
            assert_utc(item["created_at"])

    def test_list_count_is_total_before_pagination(self, api):
        assert_count_is_total(api, "/parking-areas")

    @pytest.mark.parametrize("params", [{"limit": -1}, {"offset": -1}, {"limit": "abc"}])
    def test_list_rejects_invalid_pagination(self, api, params):
        assert api.get("/parking-areas", params=params).status_code == 400

    def test_list_filters_by_name(self, api, existing_parking):
        fragment = existing_parking["name"][:3]
        body = api.get("/parking-areas", params={"name": fragment, "limit": 1000}).json()
        assert body["count"] >= 1
        assert all(fragment.lower() in item["name"].lower() for item in body["items"])

    def test_list_filters_by_bbox(self, api):
        everything = api.get("/parking-areas", params={"limit": 1}).json()["count"]
        body = assert_page(api.get("/parking-areas", params={"bbox": VALID_BBOX, "limit": 5}), 5, 0)
        assert 1 <= body["count"] <= everything

    @pytest.mark.parametrize("bbox", INVALID_BBOXES)
    def test_list_rejects_invalid_bbox(self, api, bbox):
        assert api.get("/parking-areas", params={"bbox": bbox}).status_code == 400

    def test_get_parking_area(self, api, existing_parking):
        response = api.get(f"/parking-areas/{existing_parking['parking_area_id']}")
        assert response.status_code == 200
        body = response.json()
        assert_parking(body)
        assert {field: body[field] for field in PARKING_ITEM_FIELDS} == existing_parking

    def test_get_missing_parking_area(self, api):
        assert api.get(f"/parking-areas/{MISSING_ID}").status_code == 404

    @pytest.mark.writes
    def test_create_parking_area(self, api, cleanup):
        payload = {"name": unique("Lot"), "capacity": 120, "geom": POLYGON}
        response = api.post("/parking-areas", json=payload)
        body = cleanup.track(response, "/parking-areas", "parking_area_id")
        assert response.status_code == 201, response.text
        assert_parking(body)
        assert body == {**payload, "parking_area_id": body["parking_area_id"], "created_at": body["created_at"]}
        assert api.get(f"/parking-areas/{body['parking_area_id']}").json() == body

    @pytest.mark.writes
    def test_create_with_required_fields_only(self, make_parking):
        body = make_parking()
        assert body["capacity"] is None
        assert body["geom"] == POLYGON

    @pytest.mark.writes
    def test_create_accepts_zero_capacity(self, make_parking):
        assert make_parking(capacity=0)["capacity"] == 0

    @pytest.mark.writes
    @pytest.mark.parametrize("field", ["name", "geom"])
    def test_create_requires_field(self, api, cleanup, field):
        payload = {"name": unique("Lot"), "geom": POLYGON}
        del payload[field]
        response = api.post("/parking-areas", json=payload)
        cleanup.track(response, "/parking-areas", "parking_area_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("changes", [{"name": "   "}, {"capacity": -1}])
    def test_create_rejects_invalid_field(self, api, cleanup, changes):
        response = api.post("/parking-areas", json={"name": unique("Lot"), "geom": POLYGON, **changes})
        cleanup.track(response, "/parking-areas", "parking_area_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("geom", BAD_POLYGONS)
    def test_create_rejects_bad_geometry(self, api, cleanup, geom):
        response = api.post("/parking-areas", json={"name": unique("Lot"), "geom": geom})
        cleanup.track(response, "/parking-areas", "parking_area_id")
        assert response.status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_create_rejects_malformed_json(self, api, content):
        assert send_raw(api, "POST", "/parking-areas", content).status_code == 400

    @pytest.mark.writes
    def test_list_bbox_returns_inside_touching_and_crossing(self, api, make_parking):
        tag = unique("BBOX")
        for case, geom in PARKING_BBOX_CASES.items():
            make_parking(name=f"{tag} {case}", geom=geom)
        body = api.get("/parking-areas", params={"bbox": TEST_BBOX, "name": tag, "limit": 100}).json()
        assert {item["name"] for item in body["items"]} == {f"{tag} inside", f"{tag} crosses", f"{tag} touches"}
        assert body["count"] == 3

    @pytest.mark.writes
    def test_update_partial_changes_only_supplied_fields(self, api, make_parking):
        area = make_parking(capacity=120)
        response = api.put(f"/parking-areas/{area['parking_area_id']}", json={"capacity": 150})
        assert response.status_code == 200, response.text
        assert_parking(response.json())
        assert response.json() == {**area, "capacity": 150}

    @pytest.mark.writes
    def test_update_all_fields(self, api, make_parking):
        area = make_parking()
        changes = {"name": unique("Lot"), "capacity": 80, "geom": OTHER_POLYGON}
        response = api.put(f"/parking-areas/{area['parking_area_id']}", json=changes)
        assert response.status_code == 200, response.text
        assert response.json() == {**area, **changes}

    @pytest.mark.writes
    def test_update_rejects_empty_payload(self, api, make_parking):
        area = make_parking()
        assert api.put(f"/parking-areas/{area['parking_area_id']}", json={}).status_code == 400

    @pytest.mark.writes
    @pytest.mark.parametrize("content", MALFORMED_BODIES)
    def test_update_rejects_malformed_json(self, api, make_parking, content):
        area = make_parking()
        assert send_raw(api, "PUT", f"/parking-areas/{area['parking_area_id']}", content).status_code == 400

    @pytest.mark.writes
    def test_update_missing_parking_area(self, api):
        assert api.put(f"/parking-areas/{MISSING_ID}", json={"capacity": 150}).status_code == 404

    @pytest.mark.writes
    @pytest.mark.parametrize(
        "changes",
        [{"capacity": -1}, {"name": None}, {"name": "  "}, {"geom": None}, {"geom": LINE}],
    )
    def test_update_rejects_invalid_field(self, api, make_parking, changes):
        area = make_parking()
        response = api.put(f"/parking-areas/{area['parking_area_id']}", json=changes)
        assert response.status_code == 400
        assert api.get(f"/parking-areas/{area['parking_area_id']}").json() == area

    @pytest.mark.writes
    def test_delete_parking_area(self, api, make_parking):
        area = make_parking()
        response = api.delete(f"/parking-areas/{area['parking_area_id']}")
        assert response.status_code == 200
        assert response.json() == {
            "message": "Parking area deleted successfully.",
            "parking_area_id": area["parking_area_id"],
        }
        assert api.get(f"/parking-areas/{area['parking_area_id']}").status_code == 404

    @pytest.mark.writes
    def test_delete_missing_parking_area(self, api):
        assert api.delete(f"/parking-areas/{MISSING_ID}").status_code == 404
