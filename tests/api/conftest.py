import os
import warnings
from urllib.parse import urlsplit

import httpx
import pytest

from support import unique

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
WRITES_REQUESTED = os.environ.get("ALLOW_WRITES") == "1"
API_IS_LOCAL = urlsplit(API_BASE_URL).hostname in LOCAL_HOSTS
WRITES_ENABLED = WRITES_REQUESTED and API_IS_LOCAL


def pytest_configure(config):
    config.addinivalue_line("markers", "writes: inserts, updates or deletes data through the API")


def pytest_runtest_setup(item):
    if item.get_closest_marker("writes") and not WRITES_ENABLED:
        if WRITES_REQUESTED:
            pytest.skip(f"Write tests only run against a local API, not {API_BASE_URL}")
        pytest.skip("Set ALLOW_WRITES=1 to run write tests")


def _block_unapproved_writes(request):
    if request.method != "GET" and not WRITES_ENABLED:
        raise RuntimeError(f"Blocked {request.method} {request.url}: writes are disabled")


def _is_default_not_found(response):
    try:
        return response.status_code == 404 and response.json() == {"detail": "Not Found"}
    except ValueError:
        return False


class Cleanup:
    def __init__(self):
        self.paths = []

    def add(self, path):
        self.paths.append(path)

    def track(self, response, prefix, id_field):
        try:
            body = response.json()
        except ValueError:
            return None
        if isinstance(body, dict) and isinstance(body.get(id_field), int):
            self.add(f"{prefix}/{body[id_field]}")
        return body


@pytest.fixture(scope="session")
def api():
    with httpx.Client(
        base_url=f"{API_BASE_URL}/api/v1",
        timeout=30,
        event_hooks={"request": [_block_unapproved_writes]},
    ) as client:
        yield client


@pytest.fixture(scope="session")
def require_route(api):
    reasons = {}

    def check(path):
        if path not in reasons:
            try:
                response = api.get(path, params={"limit": 1})
            except httpx.TransportError as exc:
                reasons[path] = f"API not reachable at {API_BASE_URL}: {exc}"
            else:
                reasons[path] = f"{path} is not built yet" if _is_default_not_found(response) else None
        if reasons[path]:
            pytest.skip(reasons[path])

    return check


@pytest.fixture
def cleanup(api):
    tracker = Cleanup()
    yield tracker
    for path in reversed(tracker.paths):
        response = api.delete(path)
        if response.status_code not in (200, 404):
            warnings.warn(f"Cleanup DELETE {path} returned {response.status_code}")


@pytest.fixture(scope="session")
def existing_vehicle(api, require_route):
    require_route("/vehicles")
    items = api.get("/vehicles", params={"limit": 1}).json()["items"]
    if not items:
        pytest.skip("No existing vehicle in the database")
    return items[0]


@pytest.fixture(scope="session")
def vehicle_refs(existing_vehicle):
    return {
        "vehicle_type_id": existing_vehicle["vehicle_type_id"],
        "vehicle_status_id": existing_vehicle["vehicle_status_id"],
    }


@pytest.fixture
def make_vehicle(api, vehicle_refs, cleanup):
    def create(**fields):
        payload = {**vehicle_refs, "plate_number": unique("T"), **fields}
        response = api.post("/vehicles", json=payload)
        body = cleanup.track(response, "/vehicles", "vehicle_id")
        assert response.status_code == 201, response.text
        return body

    return create
