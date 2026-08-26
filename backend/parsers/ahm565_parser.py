from core.models import AircraftEnvelope


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
