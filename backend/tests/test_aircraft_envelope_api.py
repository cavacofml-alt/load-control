import pytest
from fastapi.testclient import TestClient

import api.routes.aircraft as aircraft_module
from core.models import AircraftProfile
from main import app
from parsers.ahm565_parser import AHM565Parser

client = TestClient(app)


def _tcjnh_profile() -> AircraftProfile:
    parser = AHM565Parser("dummy")
    return AircraftProfile(
        envelope=parser.parse(),
        cabin_zones=parser.parse_cabin_zones(),
        cargo_holds=parser.parse_cargo_holds(),
    )


@pytest.fixture(autouse=True)
def mock_aircraft_repository(monkeypatch):
    profile = _tcjnh_profile()
    monkeypatch.setattr(
        aircraft_module,
        "get_aircraft_profile",
        lambda registration: profile if registration == "TC-JNH" else None,
    )


def test_get_envelope_returns_structural_limits():
    response = client.get("/api/v1/aircraft/TC-JNH")
    assert response.status_code == 200
    data = response.json()
    assert data["mzfw"] == 175000.0
    assert data["mtow"] == 233000.0
    assert data["mlaw"] == 187000.0


def test_get_envelope_unknown_registration_returns_404():
    response = client.get("/api/v1/aircraft/XX-YYY")
    assert response.status_code == 404
