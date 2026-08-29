import pytest
from fastapi.testclient import TestClient

import api.routes.loadsheets as loadsheets_module
from core.models import AircraftProfile, Flight, Loadsheet
from main import app
from parsers.ahm565_parser import AHM565Parser

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

_FLIGHT_NO_AIRCRAFT = _FLIGHT.model_copy(update={"id": "22222222-2222-2222-2222-222222222222", "aircraft_registration": None})

_DEMO_SIGNER_ID = "33333333-3333-3333-3333-333333333333"


def _tcjnh_profile() -> AircraftProfile:
    parser = AHM565Parser("dummy")
    return AircraftProfile(
        envelope=parser.parse(),
        cabin_zones=parser.parse_cabin_zones(),
        cargo_holds=parser.parse_cargo_holds(),
    )


def _fake_created_loadsheet(**overrides) -> Loadsheet:
    base = dict(
        id="44444444-4444-4444-4444-444444444444",
        flight_id=_FLIGHT.id,
        version=1,
        supersedes_id=None,
        document_type="FINAL",
        zfw=125187.0,
        tow=185187.0,
        law=153187.0,
        zfw_cg=36.35,
        zfw_mac=25.0,
        tow_cg=None,
        tow_mac=None,
        total_index=89.2,
        signed_by=_DEMO_SIGNER_ID,
        signed_at="2026-09-01T05:00:00+00:00",
    )
    base.update(overrides)
    return Loadsheet(**base)


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    profile = _tcjnh_profile()
    monkeypatch.setenv("DEMO_SIGNER_PROFILE_ID", _DEMO_SIGNER_ID)
    monkeypatch.setattr(
        loadsheets_module,
        "get_flight",
        lambda flight_id: {
            _FLIGHT.id: _FLIGHT,
            _FLIGHT_NO_AIRCRAFT.id: _FLIGHT_NO_AIRCRAFT,
        }.get(flight_id),
    )
    monkeypatch.setattr(
        loadsheets_module,
        "get_aircraft_profile",
        lambda registration: profile if registration == "TC-JNH" else None,
    )
    monkeypatch.setattr(loadsheets_module, "create_loadsheet", lambda **kwargs: _fake_created_loadsheet())
    monkeypatch.setattr(loadsheets_module, "list_loadsheets", lambda flight_id: [_fake_created_loadsheet()])


def test_sign_loadsheet_without_demo_signer_env_returns_503(monkeypatch):
    monkeypatch.delenv("DEMO_SIGNER_PROFILE_ID", raising=False)
    payload = {"flight_id": _FLIGHT.id, "take_off_fuel": 60000, "trip_fuel": 32000}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 503


def test_sign_loadsheet_within_limits_returns_200():
    payload = {"flight_id": _FLIGHT.id, "take_off_fuel": 60000, "trip_fuel": 32000}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["signed_by"] == _DEMO_SIGNER_ID
    assert data["tow_cg"] is None
    assert data["tow_mac"] is None


def test_sign_loadsheet_unknown_flight_returns_404():
    payload = {"flight_id": "does-not-exist", "take_off_fuel": 0, "trip_fuel": 0}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 404


def test_sign_loadsheet_flight_without_aircraft_returns_422():
    payload = {"flight_id": _FLIGHT_NO_AIRCRAFT.id, "take_off_fuel": 0, "trip_fuel": 0}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 422


def test_sign_loadsheet_over_limit_is_hard_blocked():
    # MTOW real do TC-JNH é 233000kg; DOW (125187) + 120000 de fuel excede-o.
    # Ao contrário de /calculate, aqui isto tem de bloquear com 422.
    payload = {"flight_id": _FLIGHT.id, "take_off_fuel": 120000, "trip_fuel": 10000}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 422


def test_sign_loadsheet_trip_fuel_over_take_off_fuel_returns_422():
    payload = {"flight_id": _FLIGHT.id, "take_off_fuel": 20000, "trip_fuel": 25000}
    response = client.post("/api/v1/loadsheets", json=payload)
    assert response.status_code == 422


def test_get_loadsheet_history_returns_versions():
    response = client.get(f"/api/v1/loadsheets/{_FLIGHT.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["version"] == 1
