from core.models import AircraftEnvelope


class AHM560Parser:
    def __init__(self, raw_data: str):
        self.raw_data = raw_data

    def parse(self) -> AircraftEnvelope:
        # TODO: Lógica de Regex para extrair secções do AHM560 (ex: AH, AL, etc.)
        # Para já, retorna dados mockados de um A320 para podermos testar o motor matemático
        return AircraftEnvelope(
            registration="CS-TQA",
            type_designator="A320-214",
            mzfw=62500.0,
            mtow=77000.0,
            mlaw=66000.0,
            dow=42500.0,
            doi=45.0,
            lemac=17.5,
            mac_length=4.19,
            k_constant=1000.0,
            c_constant=50.0
        )
