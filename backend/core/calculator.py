from core.models import AircraftEnvelope, CargoHold


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

    def calculate_lizfw(self, loads: dict[str, float], cargo_holds: list[CargoHold]) -> float:
        """Calcula o Loaded Index at Zero Fuel Weight (LIZFW).

        Soma ao DOI a contribuição de índice de cada porão carregado (deadload),
        usando o "index per weight unit" da posição: (balance_arm - reference_station) / C.
        `loads` mapeia hold_code -> peso (kg) carregado nesse porão.
        """
        holds_by_code = {hold.hold_code: hold for hold in cargo_holds}
        index_delta = 0.0
        for hold_code, weight in loads.items():
            hold = holds_by_code[hold_code]
            index_per_weight_unit = (hold.balance_arm - self.aircraft.reference_station) / self.aircraft.c_constant
            index_delta += weight * index_per_weight_unit
        return round(self.aircraft.doi + index_delta, 5)

    def check_weight_limits(self, zfw: float, tow: float, law: float) -> dict:
        """Valida os pesos contra os limites estruturais da aeronave."""
        return {
            "zfw_ok": zfw <= self.aircraft.mzfw,
            "tow_ok": tow <= self.aircraft.mtow,
            "law_ok": law <= self.aircraft.mlaw,
            "all_cleared": (zfw <= self.aircraft.mzfw) and (tow <= self.aircraft.mtow) and (law <= self.aircraft.mlaw)
        }
