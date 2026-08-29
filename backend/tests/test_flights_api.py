import pytest
from fastapi.testclient import TestClient

import api.routes.flights as flights_module
from core.models import Flight
from main import app

client = TestClient(app)

_FLIGHT = Flight(
    id="11111111-1111-1111-1111-111111111111",
    flight_number="TK1234",
    origin="LTFM",
    destination="LPPT",
    std="2026-09-01T06:30:00+00:00",
    status="SCHEDULED",
    aircraft_registration="TC-JNH",
)


def test_list_flights_returns_flights(monkeypatch):
    monkeypatch.setattr(flights_module, "list_flights", lambda: [_FLIGHT])
    response = client.get("/api/v1/flights")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["flight_number"] == "TK1234"
    assert data[0]["aircraft_registration"] == "TC-JNH"


def test_get_flight_returns_flight(monkeypatch):
    monkeypatch.setattr(flights_module, "get_flight", lambda flight_id: _FLIGHT if flight_id == _FLIGHT.id else None)
    response = client.get(f"/api/v1/flights/{_FLIGHT.id}")
    assert response.status_code == 200
    assert response.json()["id"] == _FLIGHT.id


def test_get_flight_unknown_returns_404(monkeypatch):
    monkeypatch.setattr(flights_module, "get_flight", lambda flight_id: None)
    response = client.get("/api/v1/flights/does-not-exist")
    assert response.status_code == 404


def test_list_flights_infrastructure_error_returns_503(monkeypatch):
    def boom():
        raise RuntimeError("Supabase indisponível")

    monkeypatch.setattr(flights_module, "list_flights", boom)
    response = client.get("/api/v1/flights")
    assert response.status_code == 503
