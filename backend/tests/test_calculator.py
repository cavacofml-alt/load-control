import pytest
from core.models import AircraftEnvelope, CargoHold
from core.calculator import BalanceCalculator


@pytest.fixture
def tcjnh_cargo_holds():
    # Dados reais: THY-AHM565_A330-300, Secção D2 (Lower Deck, frota 333A/333B)
    return [
        CargoHold(hold_code="CPT1", hold_type="LOWER", max_weight=10206.0, balance_arm=17.125),
        CargoHold(hold_code="CPT2", hold_type="LOWER", max_weight=20412.0, balance_arm=24.575),
        CargoHold(hold_code="CPT3", hold_type="LOWER", max_weight=9522.0, balance_arm=44.650),
        CargoHold(hold_code="CPT4", hold_type="LOWER", max_weight=10206.0, balance_arm=49.600),
        CargoHold(hold_code="CPT5", hold_type="LOWER", max_weight=3468.0, balance_arm=54.267),
    ]


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


def test_deadload_lizfw_and_maczfw(tcjnh_envelope, tcjnh_cargo_holds):
    calc = BalanceCalculator(tcjnh_envelope)

    # Carrega 2000kg no CPT1 (FWD, arm 17.125 — bem à frente da reference station
    # 36.35) e 1000kg no CPT5 (BULK, arm 54.267 — atrás da reference station).
    loads = {"CPT1": 2000.0, "CPT5": 1000.0}
    lizfw = calc.calculate_lizfw(loads, tcjnh_cargo_holds)

    # "Index per wt unit" de cada porão, tal como publicado no manual (Sheet D2):
    # CPT1 = -0.00769, CPT5 = +0.00717. A carga em CPT1 pesa mais e está mais
    # deslocada da ref station, por isso o efeito líquido é negativo (LIZFW < DOI).
    assert lizfw < tcjnh_envelope.doi

    zfw = tcjnh_envelope.dow + sum(loads.values())
    cg_zfw = calc.calculate_cg(total_weight=zfw, total_index=lizfw)
    mac_zfw = calc.calculate_mac_percentage(cg_zfw)

    # Recalcula o delta de índice de forma independente (mesma fórmula oficial
    # do AHM565: index_per_wt = (balance_arm - reference_station) / C) para
    # confirmar que calculate_lizfw não introduziu nenhum desvio.
    holds_by_code = {h.hold_code: h for h in tcjnh_cargo_holds}
    expected_delta = sum(
        weight * ((holds_by_code[code].balance_arm - tcjnh_envelope.reference_station) / tcjnh_envelope.c_constant)
        for code, weight in loads.items()
    )
    assert lizfw == round(tcjnh_envelope.doi + expected_delta, 5)

    # Com a carga a puxar o CG para a frente, o %MACZFW tem de ser diferente
    # do %MAC calculado só com o DOI (estado base, sem deadload).
    cg_dow_only = calc.calculate_cg(total_weight=tcjnh_envelope.dow, total_index=tcjnh_envelope.doi)
    mac_dow_only = calc.calculate_mac_percentage(cg_dow_only)
    assert mac_zfw != mac_dow_only
