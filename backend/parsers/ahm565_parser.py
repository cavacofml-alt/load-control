from core.models import AircraftEnvelope, CabinZone, CargoHold


class AHM565Parser:
    """Adapter para o formato AHM 565 (documento estruturado de dados semipermanentes).

    Ainda não faz parsing real do documento — devolve o perfil real do TC-JNH
    (A330-300, THY-AHM565_A330-300_Rev10) para validar o motor de cálculo
    contra dados publicados verificáveis, enquanto o parser de secções
    (C, D, E, F) não está implementado.
    """

    def __init__(self, raw_data: str):
        self.raw_data = raw_data

    def parse(self) -> AircraftEnvelope:
        # TODO: parsing real das secções C (Index/MAC formula, CG limits),
        # D (holds/cabin) e E (DOW/DOI por registration).
        return AircraftEnvelope(
            registration="TC-JNH",
            type_designator="A330-300",
            mzfw=175000.0,
            mtow=233000.0,
            mlaw=187000.0,
            dow=125187.0,
            doi=89.2,
            lemac=34.532,
            mac_length=7.27,
            k_constant=100.0,
            c_constant=2500.0,
            reference_station=36.35,
        )

    def parse_cargo_holds(self) -> list[CargoHold]:
        # TODO: parsing real da Secção D (Holds and Compartments).
        # Para já, devolve os porões reais do TC-JNH / frota 333A-B (Sheet D2, Lower Deck).
        return [
            CargoHold(hold_code="CPT1", hold_type="LOWER", max_weight=10206.0, balance_arm=17.125),
            CargoHold(hold_code="CPT2", hold_type="LOWER", max_weight=20412.0, balance_arm=24.575),
            CargoHold(hold_code="CPT3", hold_type="LOWER", max_weight=9522.0, balance_arm=44.650),
            CargoHold(hold_code="CPT4", hold_type="LOWER", max_weight=10206.0, balance_arm=49.600),
            CargoHold(hold_code="CPT5", hold_type="LOWER", max_weight=3468.0, balance_arm=54.267),
        ]

    def parse_cabin_zones(self) -> list[CabinZone]:
        # TODO: parsing real da Secção D5 (Cabin Definitions).
        # Para já, devolve as zonas reais do TC-JNH na configuração 28C/261Y
        # (Sheet D5, Main deck, frota 333A-B).
        return [
            CabinZone(zone_code="0A", max_capacity=28, balance_arm=18.820),
            CabinZone(zone_code="0B", max_capacity=138, balance_arm=33.387),
            CabinZone(zone_code="0C", max_capacity=123, balance_arm=48.865),
        ]
