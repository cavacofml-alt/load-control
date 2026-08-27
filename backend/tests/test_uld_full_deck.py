import pytest
from parsers.ahm565_parser import AHM565Parser
from core.calculator import validate_hold_overlap, validate_uld_compatibility


@pytest.fixture
def cargo_holds():
    return AHM565Parser("dummy").parse_cargo_holds()


def _hold(cargo_holds, hold_code):
    return next(h for h in cargo_holds if h.hold_code == hold_code)


def test_full_deck_maps_61_positions_across_five_holds(cargo_holds):
    # 9 baias FWD (6 com P) + 7 baias AFT (5 com P, já que a 31P foi excluída)
    # = 58 posições de ULD + 3 posições de carga solta no Bulk (CPT51-53) = 61
    total_positions = sum(len(h.uld_positions) for h in cargo_holds)
    assert total_positions == 61


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


def test_bulk_positions_have_no_uld_type_and_no_exclusion(cargo_holds):
    cpt5 = _hold(cargo_holds, "CPT5")
    codes = {p.position_code for p in cpt5.uld_positions}
    assert codes == {"CPT51", "CPT52", "CPT53"}
    for position in cpt5.uld_positions:
        assert position.allowed_ulds == {"BULK": position.allowed_ulds["BULK"]}
        assert position.mutually_exclusive_with == []


def test_bulk_positions_can_all_be_loaded_simultaneously(cargo_holds):
    cpt5 = _hold(cargo_holds, "CPT5")
    # As 3 posições do Bulk são compartimentos separados, não alternativas
    # exclusivas — carregar as três ao mesmo tempo é válido.
    validate_hold_overlap({"CPT51": 300.0, "CPT52": 1000.0, "CPT53": 1500.0}, cpt5.uld_positions)


def test_bulk_position_rejects_uld_type(cargo_holds):
    # Bulk é carga solta — não aceita nenhum tipo de ULD contentorizado.
    cpt5 = _hold(cargo_holds, "CPT5")
    hold_loads = {"CPT51": {"uld_type": "AKE", "weight": 200.0}}
    with pytest.raises(ValueError):
        validate_uld_compatibility(hold_loads, cpt5.uld_positions)


def test_bulk_position_rejects_over_its_own_limit(cargo_holds):
    cpt5 = _hold(cargo_holds, "CPT5")
    hold_loads = {"CPT51": {"uld_type": "BULK", "weight": 400.0}}  # limite real: 339kg
    with pytest.raises(ValueError):
        validate_uld_compatibility(hold_loads, cpt5.uld_positions)
