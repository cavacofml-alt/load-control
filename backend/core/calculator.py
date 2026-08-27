from core.models import AircraftEnvelope, CabinZone, CargoHold, UldPosition

# Pesos standard IATA (All flights except holiday charters) — THY AHM565 Sheet B3
STANDARD_PAX_WEIGHTS = {
    "ADULT": 84.0,
    "MALE": 88.0,
    "FEMALE": 70.0,
    "CHILD": 35.0,
    "INFANT": 10.0,
}


def validate_hold_overlap(hold_loads: dict[str, float], uld_positions: list[UldPosition]) -> None:
    """Lança ValueError se duas posições carregadas em simultâneo partilharem
    fisicamente o mesmo espaço num porão (overlap de ULD).

    `hold_loads` mapeia position_code -> peso (kg); só posições com peso > 0
    contam como "ocupadas" para efeitos de deteção de overlap.
    """
    positions_by_code = {position.position_code: position for position in uld_positions}
    occupied = {code for code, weight in hold_loads.items() if weight > 0}

    for code in occupied:
        position = positions_by_code[code]
        conflicts = set(position.mutually_exclusive_with) & occupied
        if conflicts:
            raise ValueError(
                f"Overlap de ULD: a posição '{code}' é incompatível com {sorted(conflicts)} "
                "— partilham o mesmo espaço físico no porão."
            )


def validate_uld_compatibility(hold_loads: dict[str, dict], uld_positions: list[UldPosition]) -> None:
    """Lança ValueError se uma posição for carregada com um tipo de ULD que
    não é permitido nessa posição, ou com um peso acima do limite estrutural
    específico desse tipo.

    `hold_loads` mapeia position_code -> {"uld_type": str, "weight": float}.
    """
    positions_by_code = {position.position_code: position for position in uld_positions}

    for code, load in hold_loads.items():
        position = positions_by_code[code]
        uld_type = load["uld_type"]
        weight = load["weight"]

        if uld_type not in position.allowed_ulds:
            raise ValueError(
                f"Tipo de ULD '{uld_type}' não é permitido na posição '{code}'. "
                f"Tipos permitidos: {sorted(position.allowed_ulds)}."
            )

        max_weight = position.allowed_ulds[uld_type]
        if weight > max_weight:
            raise ValueError(
                f"Peso {weight}kg excede o limite estrutural de {max_weight}kg "
                f"para '{uld_type}' na posição '{code}'."
            )


class BalanceCalculator:
    def __init__(self, aircraft: AircraftEnvelope):
        self.aircraft = aircraft

    def calculate_cg(self, total_weight: float, total_index: float) -> float:
        """Calcula o True Center of Gravity (CG) a partir do índice, peso e Reference Station."""
        if total_weight <= 0:
            raise ValueError("Total weight must be greater than zero.")

        # Reverte o Índice para o Momento usando as constantes C e K
        moment = (total_index - self.aircraft.k_constant) * self.aircraft.c_constant

        # Calcula a posição real do CG somando o desvio à Reference Station
        cg = self.aircraft.reference_station + (moment / total_weight)
        return round(cg, 5)

    def calculate_mac_percentage(self, cg: float) -> float:
        """Calcula a %MAC (Mean Aerodynamic Chord) com base no CG atual."""
        mac_perc = ((cg - self.aircraft.lemac) / self.aircraft.mac_length) * 100
        return round(mac_perc, 2)

    @staticmethod
    def _resolve_pax_weight(pax: dict[str, int] | float) -> float:
        """Resolve o peso total de uma zona de cabine: usa os pesos standard
        IATA por tipo de passageiro se `pax` for uma contagem (dict), ou usa
        diretamente o peso já fornecido quando o peso real é conhecido."""
        if isinstance(pax, dict):
            return sum(STANDARD_PAX_WEIGHTS[ptype] * count for ptype, count in pax.items())
        return float(pax)

    def calculate_pax_weight(self, pax_loads: dict[str, dict[str, int] | float]) -> float:
        """Peso total de todos os passageiros, somado por zona de cabine."""
        return sum(self._resolve_pax_weight(pax) for pax in pax_loads.values())

    def calculate_pax_influence(
        self,
        pax_loads: dict[str, dict[str, int] | float],
        cabin_zones: list[CabinZone],
    ) -> float:
        """Calcula a contribuição de índice (delta) gerada pelos passageiros.

        `pax_loads` mapeia zone_code -> contagem por tipo (ex.: {"ADULT": 20})
        ou um peso já conhecido em kg, quando o peso real dessa zona é
        fornecido diretamente em vez de usar os pesos standard IATA.
        """
        zones_by_code = {zone.zone_code: zone for zone in cabin_zones}
        index_delta = 0.0
        for zone_code, pax in pax_loads.items():
            zone = zones_by_code[zone_code]
            zone_weight = self._resolve_pax_weight(pax)
            index_per_weight_unit = (zone.balance_arm - self.aircraft.reference_station) / self.aircraft.c_constant
            index_delta += zone_weight * index_per_weight_unit
        return index_delta

    def calculate_lizfw(
        self,
        cargo_loads: dict[str, float],
        cargo_holds: list[CargoHold],
        pax_loads: dict[str, dict[str, int] | float] | None = None,
        cabin_zones: list[CabinZone] | None = None,
    ) -> float:
        """Calcula o Loaded Index at Zero Fuel Weight (LIZFW).

        Soma ao DOI a contribuição de índice da carga nos porões (deadload) e,
        opcionalmente, dos passageiros nas zonas de cabine. Cada contribuição
        usa o "index per weight unit" da posição: (balance_arm - reference_station) / C.
        `cargo_loads` mapeia hold_code -> peso (kg) carregado nesse porão.
        """
        holds_by_code = {hold.hold_code: hold for hold in cargo_holds}
        index_delta = 0.0
        for hold_code, weight in cargo_loads.items():
            hold = holds_by_code[hold_code]
            index_per_weight_unit = (hold.balance_arm - self.aircraft.reference_station) / self.aircraft.c_constant
            index_delta += weight * index_per_weight_unit

        if pax_loads:
            index_delta += self.calculate_pax_influence(pax_loads, cabin_zones or [])

        return round(self.aircraft.doi + index_delta, 5)

    def calculate_lizfw_from_positions(
        self,
        position_loads: dict[str, float],
        cargo_holds: list[CargoHold],
        pax_loads: dict[str, dict[str, int] | float] | None = None,
        cabin_zones: list[CabinZone] | None = None,
    ) -> float:
        """Como `calculate_lizfw`, mas usa o balance_arm exato de cada posição
        de ULD carregada, não a média/centroide agregado do porão (CargoHold).

        Mais preciso sempre que se conhece a posição exata onde cada ULD está
        (ex.: 24P tem arm=28.203, bem diferente do centroide médio de CPT2,
        24.575 — usar a média introduziria um erro real no índice).
        `position_loads` mapeia position_code -> peso (kg) carregado nessa posição.
        """
        positions_by_code = {
            position.position_code: position
            for hold in cargo_holds
            for position in hold.uld_positions
        }
        index_delta = 0.0
        for position_code, weight in position_loads.items():
            position = positions_by_code[position_code]
            index_per_weight_unit = (position.balance_arm - self.aircraft.reference_station) / self.aircraft.c_constant
            index_delta += weight * index_per_weight_unit

        if pax_loads:
            index_delta += self.calculate_pax_influence(pax_loads, cabin_zones or [])

        return round(self.aircraft.doi + index_delta, 5)

    def check_weight_limits(self, zfw: float, tow: float, law: float) -> dict:
        """Valida os pesos contra os limites estruturais da aeronave."""
        return {
            "zfw_ok": zfw <= self.aircraft.mzfw,
            "tow_ok": tow <= self.aircraft.mtow,
            "law_ok": law <= self.aircraft.mlaw,
            "all_cleared": (zfw <= self.aircraft.mzfw) and (tow <= self.aircraft.mtow) and (law <= self.aircraft.mlaw)
        }
