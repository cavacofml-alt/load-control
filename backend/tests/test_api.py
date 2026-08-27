import pytest
from fastapi.testclient import TestClient

import api.routes.load_control as load_control_module
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
    """Isola os testes de API do Supabase real: devolve o perfil real do
    TC-JNH para essa matrícula, e None para qualquer outra (simula 404)."""
    profile = _tcjnh_profile()

    def fake_get_aircraft_profile(registration: str):
        return profile if registration == "TC-JNH" else None

    monkeypatch.setattr(load_control_module, "get_aircraft_profile", fake_get_aircraft_profile)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200


def test_calculate_missing_fuel_fields_returns_422():
    # take_off_fuel/trip_fuel são obrigatórios
    response = client.post("/api/v1/load-control/calculate", json={"registration": "TC-JNH"})
    assert response.status_code == 422


def test_calculate_unknown_registration_returns_404():
    payload = {"registration": "XX-YYY", "take_off_fuel": 0, "trip_fuel": 0}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 404


def test_calculate_zero_fuel_returns_dow_based_weights():
    payload = {"registration": "TC-JNH", "take_off_fuel": 0, "trip_fuel": 0}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["zfw"] == 125187.0  # DOW puro do TC-JNH, sem carga/pax/combustível
    assert data["tow"] == 125187.0
    assert data["ldw"] == 125187.0
    assert data["zfw_within_limits"] is True
    assert data["within_limits"] is True


def test_calculate_fuel_produces_real_tow_and_ldw():
    payload = {"registration": "TC-JNH", "take_off_fuel": 60000, "trip_fuel": 32000}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tow"] == data["zfw"] + 60000
    assert data["ldw"] == data["tow"] - 32000


def test_calculate_trip_fuel_over_take_off_fuel_returns_422():
    payload = {"registration": "TC-JNH", "take_off_fuel": 20000, "trip_fuel": 25000}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_tow_over_limit_flags_but_does_not_block():
    # MTOW real do TC-JNH é 233000kg; DOW (125187) + 120000 de fuel excede-o.
    payload = {"registration": "TC-JNH", "take_off_fuel": 120000, "trip_fuel": 10000}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tow"] > 233000
    assert data["tow_within_limits"] is False
    assert data["within_limits"] is False


def test_calculate_valid_cargo_and_pax_returns_200():
    payload = {
        "registration": "TC-JNH",
        "take_off_fuel": 60000,
        "trip_fuel": 32000,
        "pax_loads": {"0A": {"ADULT": 20}, "0B": {"ADULT": 100}, "0C": {"ADULT": 100}},
        "hold_loads": {"11P": {"uld_type": "PMC", "weight": 4800.0}},
    }
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["zfw"] > 125187.0
    assert "lizfw" in data and "mac_zfw" in data


def test_calculate_incompatible_uld_returns_422():
    # PAG a 4800kg excede o limite real do próprio tipo (4626kg) em 11P
    payload = {
        "registration": "TC-JNH",
        "take_off_fuel": 60000,
        "trip_fuel": 32000,
        "hold_loads": {"11P": {"uld_type": "PAG", "weight": 4800.0}},
    }
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_overlap_returns_422():
    payload = {
        "registration": "TC-JNH",
        "take_off_fuel": 60000,
        "trip_fuel": 32000,
        "hold_loads": {
            "11L": {"uld_type": "AKE", "weight": 1200.0},
            "11": {"uld_type": "PLA", "weight": 3000.0},
        },
    }
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_unknown_position_returns_422():
    payload = {
        "registration": "TC-JNH",
        "take_off_fuel": 60000,
        "trip_fuel": 32000,
        "hold_loads": {"99Z": {"uld_type": "AKE", "weight": 1000.0}},
    }
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_aircraft_profile_endpoint_accepts_valid_payload():
    payload = {
        "envelope": {
            "registration": "TC-JNH",
            "type_designator": "A330-300",
            "mzfw": 175000.0,
            "mtow": 233000.0,
            "mlaw": 187000.0,
            "dow": 125187.0,
            "doi": 89.2,
            "lemac": 34.532,
            "mac_length": 7.27,
            "k_constant": 100.0,
            "c_constant": 2500.0,
            "reference_station": 36.35,
        }
    }
    response = client.post("/api/v1/aircraft/profile", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "valid", "registration": "TC-JNH"}


def test_aircraft_profile_endpoint_rejects_invalid_payload():
    response = client.post("/api/v1/aircraft/profile", json={"envelope": {"registration": "TC-JNH"}})
    assert response.status_code == 422
