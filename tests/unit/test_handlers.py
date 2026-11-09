"""Offline regressions for the request boundary and HTTP contract."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from backend.dao.vehicle import VehicleDAO
from backend.handler.validation import geometry, timestamp
from backend.main import app

client = TestClient(app)


def test_tracking_and_assignment_operations_are_registered():
    operations = {
        (method, path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api/v1")
        for method in methods
    }
    assert len(operations) == 28


@pytest.mark.parametrize("value", [True, "1", 1.5, 0, -1, 2**63])
def test_invalid_vehicle_ids_never_reach_database(monkeypatch, value):
    create = Mock()
    monkeypatch.setattr(VehicleDAO, "create_vehicle", create)
    result = client.post(
        "/api/v1/vehicles",
        json={
            "vehicle_type_id": value,
            "vehicle_status_id": 1,
            "plate_number": "TEST",
        },
    )
    assert result.status_code == 400
    create.assert_not_called()


@pytest.mark.parametrize("coordinate", [True, "1", float("nan"), float("inf")])
def test_point_rejects_nonfinite_or_non_numeric_coordinates(coordinate):
    with pytest.raises(ValueError):
        geometry({"type": "Point", "coordinates": [coordinate, 0]}, "Point")


@pytest.mark.parametrize(
    "value",
    ["2026-03-14", "yesterday", "2026-13-14T00:00:00Z", "2026-01-01T00:00:00.1234567Z"],
)
def test_timestamps_reject_invalid_or_lossy_values(value):
    with pytest.raises(ValueError):
        timestamp(value)


def test_timestamp_normalizes_offsets():
    assert timestamp("2026-03-14T11:30:00-04:00") == datetime(2026, 3, 14, 15, 30)


def test_optional_null_is_preserved(monkeypatch):
    update = Mock(return_value={"vehicle_id": 1, "make": None})
    monkeypatch.setattr(VehicleDAO, "update_vehicle", update)
    result = client.put("/api/v1/vehicles/1", json={"make": None})
    assert result.status_code == 200
    update.assert_called_once_with(1, make=None)


def test_database_error_does_not_leak_credentials(monkeypatch):
    monkeypatch.setattr(
        VehicleDAO,
        "get_vehicle",
        Mock(side_effect=OperationalError("password=secret SQL SELECT")),
    )
    result = client.get("/api/v1/vehicles/1")
    assert result.status_code == 500
    assert result.json() == {"detail": "Database operation failed."}


def test_no_ping_returns_truly_empty_response(monkeypatch):
    monkeypatch.setattr(
        VehicleDAO, "get_current_location", Mock(return_value={"last_ts": None})
    )
    result = client.get("/api/v1/vehicles/1/current-location")
    assert result.status_code == 204
    assert result.content == b""


@pytest.mark.parametrize(
    "query", ["limit=9223372036854775808", "offset=1.5", "limit=-1"]
)
def test_invalid_pagination_never_reaches_database(monkeypatch, query):
    listing = Mock()
    monkeypatch.setattr(VehicleDAO, "list_vehicles", listing)
    assert client.get("/api/v1/vehicles?" + query).status_code == 400
    listing.assert_not_called()


def test_count_uses_unpaginated_filters(monkeypatch):
    listing = Mock(return_value=[])
    count = Mock(return_value=5)
    monkeypatch.setattr(VehicleDAO, "list_vehicles", listing)
    monkeypatch.setattr(VehicleDAO, "count_vehicles", count)
    result = client.get(
        "/api/v1/vehicles?limit=0&offset=9&status=active&plate_number=ABC"
    )
    assert result.json() == {"items": [], "limit": 0, "offset": 9, "count": 5}
    count.assert_called_once_with(status="active", plate_number="ABC")


@pytest.mark.parametrize(
    "path",
    ["vehicles", "location-pings", "trips", "drivers", "vehicle-assignments"],
)
def test_unknown_update_field_returns_400(path):
    assert (
        client.put(f"/api/v1/{path}/1", json={"unexpected": "value"}).status_code == 400
    )
