from dataclasses import dataclass

from core.calculator import BalanceCalculator
from core.load_service import LoadService
from core.models import AircraftProfile


@dataclass
class CalculationResult:
    """Resultado completo de um cálculo de carga — usado tanto pela pré-visualização
    (`/calculate`) como pela assinatura de loadsheet (`/loadsheets`), para garantir
    que os dois caminhos nunca calculam pesos/índice de forma diferente.

    `tow_cg`/`tow_mac` ficam sempre a `None`: o motor ainda não corrige o
    índice/CG pelo efeito do combustível (tabela de índice por tanque,
    Secção C do AHM565, não implementada). Ver comentário em `BalanceCalculator.calculate_tow`.
    """

    zfw: float
    tow: float
    ldw: float
    lizfw: float
    cg_zfw: float
    mac_zfw: float
    tow_cg: None
    tow_mac: None
    zfw_within_limits: bool
    tow_within_limits: bool
    ldw_within_limits: bool
    within_limits: bool


def run_calculation(
    profile: AircraftProfile,
    take_off_fuel: float,
    trip_fuel: float,
    pax_loads: dict[str, dict[str, int] | float] | None,
    hold_loads: dict[str, dict],
) -> CalculationResult:
    """Fonte única de verdade para o cálculo de ZFW/TOW/LDW/índice/%MAC.

    Lança `ValueError` para qualquer violação de validação (trip fuel acima
    do take-off fuel, overlap/incompatibilidade de ULD) — quem chama decide
    o código HTTP (422 tanto em `/calculate` como em `/loadsheets`).
    """
    if trip_fuel > take_off_fuel:
        raise ValueError(f"Trip fuel ({trip_fuel}kg) não pode exceder o Take-Off fuel ({take_off_fuel}kg).")

    envelope, cargo_holds, cabin_zones = profile.envelope, profile.cargo_holds, profile.cabin_zones
    calculator = BalanceCalculator(envelope)
    service = LoadService(calculator)

    lizfw = service.calculate_validated_lizfw(hold_loads, cargo_holds, pax_loads or None, cabin_zones)

    pax_weight = calculator.calculate_pax_weight(pax_loads) if pax_loads else 0.0
    cargo_weight = sum(item["weight"] for item in hold_loads.values())
    zfw = envelope.dow + cargo_weight + pax_weight

    cg_zfw = calculator.calculate_cg(total_weight=zfw, total_index=lizfw)
    mac_zfw = calculator.calculate_mac_percentage(cg_zfw)

    tow = calculator.calculate_tow(zfw, take_off_fuel)
    ldw = calculator.calculate_ldw(tow, trip_fuel)

    limits = calculator.check_weight_limits(zfw=zfw, tow=tow, law=ldw)

    return CalculationResult(
        zfw=zfw,
        tow=tow,
        ldw=ldw,
        lizfw=lizfw,
        cg_zfw=cg_zfw,
        mac_zfw=mac_zfw,
        tow_cg=None,
        tow_mac=None,
        zfw_within_limits=limits["zfw_ok"],
        tow_within_limits=limits["tow_ok"],
        ldw_within_limits=limits["law_ok"],
        within_limits=limits["all_cleared"],
    )
