import pytest
from parsers.ahm565_parser import AHM565Parser
from core.calculator import BalanceCalculator, validate_uld_compatibility
from core.load_service import LoadService


@pytest.fixture
def envelope():
    return AHM565Parser("dummy").parse()


@pytest.fixture
def cargo_holds():
    return AHM565Parser("dummy").parse_cargo_holds()


def _all_positions(cargo_holds):
    return [position for hold in cargo_holds for position in hold.uld_positions]


def test_pag_over_its_own_limit_rejected(cargo_holds):
    # 11P aceita PAG, mas o limite estrutural do PAG é 4626kg, não o do PMC (5103kg)
    positions = _all_positions(cargo_holds)
    hold_loads = {"11P": {"uld_type": "PAG", "weight": 4800.0}}
    with pytest.raises(ValueError):
        validate_uld_compatibility(hold_loads, positions)


def test_pmc_same_weight_accepted(cargo_holds):
    # O mesmo peso (4800kg) é válido para um PMC (limite 5103kg) na mesma posição
    positions = _all_positions(cargo_holds)
    hold_loads = {"11P": {"uld_type": "PMC", "weight": 4800.0}}
    validate_uld_compatibility(hold_loads, positions)  # não deve levantar exceção


def test_disallowed_uld_type_rejected(cargo_holds):
    # PMC não cabe fisicamente numa posição lateral (baseplate LD3, só AKE/PKC)
    positions = _all_positions(cargo_holds)
    hold_loads = {"11L": {"uld_type": "PMC", "weight": 1000.0}}
    with pytest.raises(ValueError):
        validate_uld_compatibility(hold_loads, positions)


def test_load_service_blocks_on_incompatible_uld(envelope, cargo_holds):
    service = LoadService(BalanceCalculator(envelope))
    hold_loads = {"11P": {"uld_type": "PAG", "weight": 4800.0}}
    with pytest.raises(ValueError):
        service.calculate_validated_lizfw(hold_loads, cargo_holds)


def test_load_service_blocks_on_overlap(envelope, cargo_holds):
    service = LoadService(BalanceCalculator(envelope))
    hold_loads = {
        "11L": {"uld_type": "AKE", "weight": 1200.0},
        "11": {"uld_type": "PLA", "weight": 3000.0},
    }
    with pytest.raises(ValueError):
        service.calculate_validated_lizfw(hold_loads, cargo_holds)


def test_load_service_computes_lizfw_when_valid(envelope, cargo_holds):
    service = LoadService(BalanceCalculator(envelope))
    hold_loads = {"11P": {"uld_type": "PMC", "weight": 4800.0}}
    lizfw = service.calculate_validated_lizfw(hold_loads, cargo_holds)

    # Recalcula de forma independente usando o balance_arm exato de 11P
    # (15.885), não a média do porão CPT1 (17.125) — confirma a precisão.
    positions = _all_positions(cargo_holds)
    position_11p = next(p for p in positions if p.position_code == "11P")
    expected_delta = 4800.0 * ((position_11p.balance_arm - envelope.reference_station) / envelope.c_constant)
    assert lizfw == round(envelope.doi + expected_delta, 5)


def test_load_service_uses_position_arm_not_hold_average(envelope, cargo_holds):
    # A mesma carga calculada com o centroide médio do porão (CPT1=17.125)
    # em vez do balance_arm exato de 11P (15.885) dava um LIZFW diferente —
    # confirma que a precisão por posição está mesmo a ser usada.
    service = LoadService(BalanceCalculator(envelope))
    hold_loads = {"11P": {"uld_type": "PMC", "weight": 4800.0}}
    lizfw = service.calculate_validated_lizfw(hold_loads, cargo_holds)

    cpt1 = next(h for h in cargo_holds if h.hold_code == "CPT1")
    hold_level_delta = 4800.0 * ((cpt1.balance_arm - envelope.reference_station) / envelope.c_constant)
    hold_level_lizfw = round(envelope.doi + hold_level_delta, 5)

    assert lizfw != hold_level_lizfw
