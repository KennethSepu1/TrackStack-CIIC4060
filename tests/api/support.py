from datetime import datetime
from uuid import uuid4

import pytest

PAGE_FIELDS = {"items", "limit", "offset", "count"}
MISSING_ID = 999_999_999
MALFORMED_BODIES = [b'{"broken": ', b"[]"]
VALID_BBOX = "-67.2100,18.1800,-67.1200,18.2600"
TEST_BBOX = "-10,-10,-9,-9"
INVALID_BBOXES = [
    "-67.21,18.18,-67.12",
    "-67.21,18.18,-67.12,18.26,1",
    "a,b,c,d",
    "-67.12,18.18,-67.12,18.26",
    "-67.12,18.18,-67.21,18.26",
    "-67.21,18.18,-67.12,91",
    "-181,18.18,-67.12,18.26",
]


def unique(prefix):
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def assert_utc(value):
    assert isinstance(value, str) and value.endswith("Z"), value
    datetime.fromisoformat(value[:-1] + "+00:00")


def send_raw(api, method, path, content):
    return api.request(method, path, content=content, headers={"Content-Type": "application/json"})


def first_item(api, require_route, path):
    require_route(path)
    items = api.get(path, params={"limit": 1}).json()["items"]
    if not items:
        pytest.skip(f"No existing rows at {path}")
    return items[0]


def assert_page(response, limit, offset, fields=PAGE_FIELDS):
    assert response.status_code == 200
    body = response.json()
    assert set(body) == fields
    assert body["limit"] == limit
    assert body["offset"] == offset
    assert len(body["items"]) <= limit
    return body


def assert_count_is_total(api, path, **params):
    one = api.get(path, params={**params, "limit": 1}).json()
    two = api.get(path, params={**params, "limit": 2}).json()
    if two["count"] < 2:
        pytest.skip(f"Need at least two rows at {path}")
    assert len(one["items"]) == 1
    assert one["count"] == two["count"]


def assert_point(geom):
    assert geom["type"] == "Point"
    lon, lat = geom["coordinates"]
    assert -180 <= lon <= 180
    assert -90 <= lat <= 90
