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

        NOTA: o LIZFW resultante usa o balance_arm agregado do porão (CargoHold),
        não o balance_arm exato de cada posição de ULD — é uma aproximação
        conhecida enquanto `calculate_lizfw` trabalhar ao nível do porão.
        """
        all_positions = [position for hold in cargo_holds for position in hold.uld_positions]

        weights_by_position = {code: load["weight"] for code, load in hold_loads.items()}
        validate_hold_overlap(weights_by_position, all_positions)
        validate_uld_compatibility(hold_loads, all_positions)

        cargo_loads_by_hold = self._aggregate_by_hold(hold_loads, cargo_holds)
        return self.calculator.calculate_lizfw(cargo_loads_by_hold, cargo_holds, pax_loads, cabin_zones)

    @staticmethod
    def _aggregate_by_hold(hold_loads: dict[str, dict], cargo_holds: list[CargoHold]) -> dict[str, float]:
        """Soma o peso das posições de ULD carregadas para o peso total de
        cada porão — necessário porque `calculate_lizfw` trabalha ao nível
        do porão (CargoHold), não da posição individual."""
        hold_code_by_position = {
            position.position_code: hold.hold_code
            for hold in cargo_holds
            for position in hold.uld_positions
        }
        totals: dict[str, float] = {}
        for code, load in hold_loads.items():
            hold_code = hold_code_by_position[code]
            totals[hold_code] = totals.get(hold_code, 0.0) + load["weight"]
        return totals
