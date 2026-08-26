from core.models import AircraftEnvelope


class AHM560Parser:
    """Adapter para o formato AHM 560 (mensagem telex de dados semipermanentes).

    Esqueleto para trabalho futuro — a estrutura de linhas/campos telex
    ainda não está definida. Não usar em produção.
    """

    def __init__(self, raw_data: str):
        self.raw_data = raw_data

    def parse(self) -> AircraftEnvelope:
        raise NotImplementedError("Parsing de telex AHM 560 ainda não implementado.")
