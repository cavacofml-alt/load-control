from core.models import AircraftEnvelope


class BalanceCalculator:
    def __init__(self, aircraft: AircraftEnvelope):
        self.aircraft = aircraft

    def calculate_cg(self, total_weight: float, total_index: float) -> float:
        """Calcula o Center of Gravity (CG) a partir do índice e peso total."""
        if total_weight <= 0:
            raise ValueError("Total weight must be greater than zero.")

        # Reverte o Índice para o Momento usando as constantes C e K da aeronave
        moment = (total_index - self.aircraft.k_constant) * self.aircraft.c_constant

        # Calcula o Centro de Gravidade
        cg = moment / total_weight
        return round(cg, 5)

    def calculate_mac_percentage(self, cg: float) -> float:
        """Calcula a %MAC (Mean Aerodynamic Chord) com base no CG atual."""
        mac_perc = ((cg - self.aircraft.lemac) / self.aircraft.mac_length) * 100
        return round(mac_perc, 2)
