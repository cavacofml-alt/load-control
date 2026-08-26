import pytest
from core.models import UldPosition
from core.calculator import validate_hold_overlap


@pytest.fixture
def cpt1_positions():
    # Dados reais: THY-AHM565_A330-300, Sheet D3 (Hold FORWARD, baia 11)
    return [
        UldPosition(position_code="11L", allowed_ulds={"AKE": 1587.0, "PKC": 1587.0}, balance_arm=15.432, mutually_exclusive_with=["11", "11P"]),
        UldPosition(position_code="11R", allowed_ulds={"AKE": 1587.0, "PKC": 1587.0}, balance_arm=15.432, mutually_exclusive_with=["11", "11P"]),
        UldPosition(position_code="11", allowed_ulds={"PLA": 3174.0}, balance_arm=15.432, mutually_exclusive_with=["11L", "11R", "11P"]),
        UldPosition(position_code="11P", allowed_ulds={"PAG": 4626.0, "PMC": 5103.0}, balance_arm=15.885, mutually_exclusive_with=["11L", "11R", "11"]),
    ]


def test_laterals_can_coexist(cpt1_positions):
    # 11L e 11R são posições laterais independentes — não partilham espaço.
    validate_hold_overlap({"11L": 1200.0, "11R": 1300.0}, cpt1_positions)


def test_single_lateral_ok(cpt1_positions):
    validate_hold_overlap({"11L": 1200.0}, cpt1_positions)


def test_single_central_pla_ok(cpt1_positions):
    validate_hold_overlap({"11": 3000.0}, cpt1_positions)


def test_single_central_pallet_ok(cpt1_positions):
    validate_hold_overlap({"11P": 4600.0}, cpt1_positions)


def test_lateral_blocks_central_pla(cpt1_positions):
    with pytest.raises(ValueError):
        validate_hold_overlap({"11L": 1200.0, "11": 3000.0}, cpt1_positions)


def test_lateral_blocks_central_pallet(cpt1_positions):
    with pytest.raises(ValueError):
        validate_hold_overlap({"11R": 1200.0, "11P": 4000.0}, cpt1_positions)


def test_central_positions_block_each_other(cpt1_positions):
    with pytest.raises(ValueError):
        validate_hold_overlap({"11": 3000.0, "11P": 4000.0}, cpt1_positions)


def test_zero_weight_position_is_not_occupied(cpt1_positions):
    # Peso 0 numa posição não conta como ocupada — não deve gerar conflito.
    validate_hold_overlap({"11L": 1200.0, "11": 0.0}, cpt1_positions)
