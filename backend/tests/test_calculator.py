import pytest
from core.models import AircraftEnvelope
from core.calculator import BalanceCalculator


@pytest.fixture
def tcjnh_envelope():
    # Dados reais: Turkish Airlines AHM565, A330-300, registration TC-JNH
    # (THY-AHM565_A330-300_Rev10_12Sep2023.pdf, Secções C4/E5/F1)
    return AircraftEnvelope(
        registration="TC-JNH",
        type_designator="A330-300",
        mzfw=175000.0,
        mtow=233000.0,
        mlaw=187000.0,
        dow=125187.0,
        doi=89.2,
        reference_station=36.35,
        lemac=34.532,
        mac_length=7.27,
        k_constant=100.0,
        c_constant=2500.0,
    )


def test_cg_and_mac_calculation(tcjnh_envelope):
    calc = BalanceCalculator(tcjnh_envelope)

    # Ponto real publicado no manual (Secção C, Sheet 5 — CG Limits, frota 333A):
    # a ZFW=175000kg, o limite forward é %MAC=19.3 / Index=70.83.
    cg = calc.calculate_cg(total_weight=175000.0, total_index=70.83)
    mac = calc.calculate_mac_percentage(cg)

    # CG deve cair dentro do envelope físico do MAC (entre o LEMAC e LEMAC+mac_length)
    assert tcjnh_envelope.lemac < cg < tcjnh_envelope.lemac + tcjnh_envelope.mac_length
    # Tolerância alinhada com a nota do próprio manual (+/- 0.3 de índice é aceitável)
    assert abs(mac - 19.3) < 0.1


def test_weight_limits(tcjnh_envelope):
    calc = BalanceCalculator(tcjnh_envelope)
    limits = calc.check_weight_limits(zfw=170000.0, tow=230000.0, law=185000.0)
    assert limits["all_cleared"] is True

    # Testar falha de MTOW (limite real: 233000 kg)
    limits_overweight = calc.check_weight_limits(zfw=170000.0, tow=234000.0, law=185000.0)
    assert limits_overweight["tow_ok"] is False
    assert limits_overweight["all_cleared"] is False
