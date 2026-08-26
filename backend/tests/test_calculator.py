import pytest
from core.models import AircraftEnvelope
from core.calculator import BalanceCalculator


@pytest.fixture
def a320_envelope():
    # Dados realistas aproximados de um A320
    return AircraftEnvelope(
        registration="CS-TQA",
        type_designator="A320-214",
        mzfw=62500.0,
        mtow=77000.0,
        mlaw=66000.0,
        dow=42500.0,
        doi=45.0,
        reference_station=16.0,  # Metros a partir do nariz
        lemac=17.5,
        mac_length=4.19,
        k_constant=50.0,
        c_constant=1000.0
    )


def test_cg_and_mac_calculation(a320_envelope):
    calc = BalanceCalculator(a320_envelope)

    # Usando um total_index de 198.0, matematicamente o CG deve cair
    # perto dos 18.55m, resultando num MAC de aproximadamente 25.1%.
    cg = calc.calculate_cg(total_weight=58000.0, total_index=198.0)
    mac = calc.calculate_mac_percentage(cg)

    assert cg > 16.0
    assert 15.0 <= mac <= 40.0

    # Validação estrita do resultado esperado
    assert round(mac, 1) == 25.1


def test_weight_limits(a320_envelope):
    calc = BalanceCalculator(a320_envelope)
    limits = calc.check_weight_limits(zfw=60000.0, tow=75000.0, law=65000.0)
    assert limits["all_cleared"] is True

    # Testar falha de MTOW
    limits_overweight = calc.check_weight_limits(zfw=60000.0, tow=78000.0, law=65000.0)
    assert limits_overweight["tow_ok"] is False
    assert limits_overweight["all_cleared"] is False
