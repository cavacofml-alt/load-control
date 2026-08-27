from core.calculator import BalanceCalculator, validate_hold_overlap, validate_uld_compatibility
from core.models import CabinZone, CargoHold


class LoadService:
    """Gatekeeper de carregamento: valida overlap físico e compatibilidade de
    tipo/peso de ULD antes de permitir qualquer cálculo. Só chama o
    `BalanceCalculator` se ambas as validações passarem."""

    def __init__(self, calculator: BalanceCalculator):
        self.calculator = calculator

    def calculate_validated_lizfw(
        self,
        hold_loads: dict[str, dict],
        cargo_holds: list[CargoHold],
        pax_loads: dict[str, dict[str, int] | float] | None = None,
        cabin_zones: list[CabinZone] | None = None,
    ) -> float:
        """`hold_loads` mapeia position_code -> {"uld_type": str, "weight": float}.

        Usa `calculate_lizfw_from_positions` — o balance_arm exato de cada
        posição de ULD, não a média/centroide agregado do porão (CargoHold).
        """
        all_positions = [position for hold in cargo_holds for position in hold.uld_positions]

        weights_by_position = {code: load["weight"] for code, load in hold_loads.items()}
        validate_hold_overlap(weights_by_position, all_positions)
        validate_uld_compatibility(hold_loads, all_positions)

        return self.calculator.calculate_lizfw_from_positions(weights_by_position, cargo_holds, pax_loads, cabin_zones)
