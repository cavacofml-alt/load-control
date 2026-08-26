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
    assert lizfw != envelope.doi
