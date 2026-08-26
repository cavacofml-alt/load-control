import pytest
from parsers.ahm565_parser import AHM565Parser
from core.calculator import validate_hold_overlap


@pytest.fixture
def cargo_holds():
    return AHM565Parser("dummy").parse_cargo_holds()


def _hold(cargo_holds, hold_code):
    return next(h for h in cargo_holds if h.hold_code == hold_code)


def test_full_deck_maps_58_positions_across_four_holds(cargo_holds):
    # 9 baias FWD (6 com P) + 7 baias AFT (5 com P, já que a 31P foi excluída) = 58 posições
    total_positions = sum(len(h.uld_positions) for h in cargo_holds)
    assert total_positions == 58


def test_bay_24_exclusion_in_cpt2(cargo_holds):
    cpt2 = _hold(cargo_holds, "CPT2")
    with pytest.raises(ValueError):
        validate_hold_overlap({"24L": 1200.0, "24P": 4000.0}, cpt2.uld_positions)


def test_bay_42_exclusion_in_cpt4(cargo_holds):
    cpt4 = _hold(cargo_holds, "CPT4")
    with pytest.raises(ValueError):
        validate_hold_overlap({"42R": 1200.0, "42": 3000.0}, cpt4.uld_positions)


def test_bay_24_laterals_coexist(cargo_holds):
    cpt2 = _hold(cargo_holds, "CPT2")
    validate_hold_overlap({"24L": 1200.0, "24R": 1300.0}, cpt2.uld_positions)


def test_bay_without_pallet_position_has_no_p_code(cargo_holds):
    # Baias 13 (CPT1), 25/26 (CPT2), 34 (CPT3) e 43 (CPT4) não têm posição P
    cpt1 = _hold(cargo_holds, "CPT1")
    codes = {p.position_code for p in cpt1.uld_positions}
    assert "13P" not in codes
    assert {"13L", "13R", "13"}.issubset(codes)


def test_31p_excluded_for_tcjnh_ldcrc(cargo_holds):
    # TC-JNH é 333A: a posição 31P está ocupada pelo LDCRC e não é carregável.
    cpt3 = _hold(cargo_holds, "CPT3")
    codes = {p.position_code for p in cpt3.uld_positions}
    assert "31P" not in codes
    assert {"31L", "31R", "31"}.issubset(codes)


def test_cross_hold_positions_do_not_interfere(cargo_holds):
    # Posições de porões diferentes (CPT1 vs CPT2) não devem ter exclusões
    # cruzadas — o overlap só existe dentro da mesma baia física.
    cpt1 = _hold(cargo_holds, "CPT1")
    position_11l = next(p for p in cpt1.uld_positions if p.position_code == "11L")
    assert "21L" not in position_11l.mutually_exclusive_with
