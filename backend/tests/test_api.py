from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200


def test_calculate_empty_payload_returns_dow_based_zfw():
    response = client.post("/api/v1/load-control/calculate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["zfw"] == 125187.0  # DOW puro do TC-JNH, sem carga/pax
    assert data["zfw_within_limits"] is True


def test_calculate_valid_cargo_and_pax_returns_200():
    payload = {
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
    payload = {"hold_loads": {"11P": {"uld_type": "PAG", "weight": 4800.0}}}
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_overlap_returns_422():
    payload = {
        "hold_loads": {
            "11L": {"uld_type": "AKE", "weight": 1200.0},
            "11": {"uld_type": "PLA", "weight": 3000.0},
        }
    }
    response = client.post("/api/v1/load-control/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_unknown_position_returns_422():
    payload = {"hold_loads": {"99Z": {"uld_type": "AKE", "weight": 1000.0}}}
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
