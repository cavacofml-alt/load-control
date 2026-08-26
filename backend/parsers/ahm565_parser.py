from core.models import AircraftEnvelope, CabinZone, CargoHold, UldPosition

# Pesos máximos estruturais por tipo de ULD (Sheet B5 "ULD Specifications" —
# valores GLOBAIS por tipo, constantes em todas as baias do Lower Deck, não
# variam por posição). Uma posição "P" aceita tanto PAG como PMC, cada um com
# o seu próprio limite — não um único limite genérico para a posição.
LATERAL_ALLOWED_ULDS = {"AKE": 1587.0, "PKC": 1587.0}
CENTRAL_ALLOWED_ULDS = {"PLA": 3174.0}
PALLET_ALLOWED_ULDS = {"PAG": 4626.0, "PMC": 5103.0}

# (bay_number, centroid L/R/central, centroid P ou None se a baia não tiver
# posição de palete grande, hold_code do porão a que a baia pertence)
FORWARD_HOLD_BAYS = [
    ("11", 15.432, 15.885, "CPT1"),
    ("12", 17.218, 18.349, "CPT1"),
    ("13", 18.801, None, "CPT1"),
    ("21", 20.563, 20.812, "CPT2"),
    ("22", 22.146, 23.276, "CPT2"),
    ("23", 23.728, 25.740, "CPT2"),
    ("24", 25.491, 28.203, "CPT2"),
    ("25", 27.073, None, "CPT2"),
    ("26", 28.655, None, "CPT2"),
]

AFT_HOLD_BAYS = [
    # 31P excluído de propósito: na frota 333A/333B (grupo de registration do
    # TC-JNH), essa posição está ocupada pelo Lower Deck Crew Rest Container
    # (LDCRC) e não está disponível para carga (Sheet D3, nota da AFT hold).
    ("31", 40.889, None, "CPT3"),
    ("32", 43.352, 43.805, "CPT3"),
    ("33", 44.935, 46.065, "CPT3"),
    ("34", 46.517, None, "CPT3"),
    ("41", 48.077, 48.326, "CPT4"),
    ("42", 49.659, 50.790, "CPT4"),
    ("43", 51.241, None, "CPT4"),
]


def _build_bay_positions(bay_number: str, centroid_lr: float, centroid_p: float | None) -> list[UldPosition]:
    """Gera as posições de uma baia (L, R, central, e P se existir) com as
    exclusões mútuas corretas: as laterais (L/R) são independentes entre si
    mas bloqueiam a central e a P; a central e a P bloqueiam tudo o resto
    da baia (paletes de largura total)."""
    codes = [f"{bay_number}L", f"{bay_number}R", bay_number]
    if centroid_p is not None:
        codes.append(f"{bay_number}P")

    positions = []
    for code in codes:
        if code.endswith("P"):
            allowed_ulds, balance_arm = PALLET_ALLOWED_ULDS, centroid_p
            exclusions = [c for c in codes if c != code]
        elif code == f"{bay_number}L" or code == f"{bay_number}R":
            allowed_ulds, balance_arm = LATERAL_ALLOWED_ULDS, centroid_lr
            # As laterais não se excluem entre si, só com a central e a P
            exclusions = [c for c in codes if c != code and c not in (f"{bay_number}L", f"{bay_number}R")]
        else:
            allowed_ulds, balance_arm = CENTRAL_ALLOWED_ULDS, centroid_lr
            exclusions = [c for c in codes if c != code]

        positions.append(
            UldPosition(position_code=code, balance_arm=balance_arm, allowed_ulds=dict(allowed_ulds), mutually_exclusive_with=exclusions)
        )
    return positions


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
        # Para já, devolve os porões reais do TC-JNH / frota 333A-B (Sheet D2,
        # Lower Deck), com o mapa completo de posições de ULD (Sheet D3/D3.1)
        # associado a cada porão.
        positions_by_hold: dict[str, list[UldPosition]] = {"CPT1": [], "CPT2": [], "CPT3": [], "CPT4": []}
        for bay_number, centroid_lr, centroid_p, hold_code in FORWARD_HOLD_BAYS + AFT_HOLD_BAYS:
            positions_by_hold[hold_code].extend(_build_bay_positions(bay_number, centroid_lr, centroid_p))

        return [
            CargoHold(hold_code="CPT1", hold_type="LOWER", max_weight=10206.0, balance_arm=17.125, uld_positions=positions_by_hold["CPT1"]),
            CargoHold(hold_code="CPT2", hold_type="LOWER", max_weight=20412.0, balance_arm=24.575, uld_positions=positions_by_hold["CPT2"]),
            CargoHold(hold_code="CPT3", hold_type="LOWER", max_weight=9522.0, balance_arm=44.650, uld_positions=positions_by_hold["CPT3"]),
            CargoHold(hold_code="CPT4", hold_type="LOWER", max_weight=10206.0, balance_arm=49.600, uld_positions=positions_by_hold["CPT4"]),
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
