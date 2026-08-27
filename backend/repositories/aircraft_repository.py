import os
from functools import lru_cache

from supabase import Client, create_client

from core.models import AircraftEnvelope, AircraftProfile, CabinZone, CargoHold, UldPosition


@lru_cache
def _client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def get_aircraft_profile(registration: str) -> AircraftProfile | None:
    """Vai buscar o perfil completo de uma aeronave ao Supabase pela
    matrícula, reconstruindo o `AircraftProfile` a partir das tabelas
    relacionais (aircraft, cabin_zones, cargo_holds, uld_positions).

    Devolve `None` se a matrícula não existir — quem chama decide o que
    fazer com isso (ex.: o endpoint devolve 404).
    """
    client = _client()

    aircraft_rows = client.table("aircraft").select("*").eq("registration", registration).execute().data
    if not aircraft_rows:
        return None
    aircraft_row = aircraft_rows[0]

    envelope = AircraftEnvelope(
        registration=aircraft_row["registration"],
        type_designator=aircraft_row["type_designator"],
        mzfw=aircraft_row["mzfw"],
        mtow=aircraft_row["mtow"],
        mlaw=aircraft_row["mlaw"],
        dow=aircraft_row["dow"],
        doi=aircraft_row["doi"],
        lemac=aircraft_row["lemac"],
        mac_length=aircraft_row["mac_length"],
        k_constant=aircraft_row["k_constant"],
        c_constant=aircraft_row["c_constant"],
        reference_station=aircraft_row["reference_station"],
    )

    cabin_zone_rows = client.table("cabin_zones").select("*").eq("aircraft_id", aircraft_row["id"]).execute().data
    cabin_zones = [
        CabinZone(zone_code=row["zone_code"], max_capacity=row["max_capacity"], balance_arm=row["balance_arm"])
        for row in cabin_zone_rows
    ]

    cargo_hold_rows = client.table("cargo_holds").select("*").eq("aircraft_id", aircraft_row["id"]).execute().data
    hold_ids = [row["id"] for row in cargo_hold_rows]
    position_rows = (
        client.table("uld_positions").select("*").in_("cargo_hold_id", hold_ids).execute().data if hold_ids else []
    )
    positions_by_hold_id: dict[str, list[dict]] = {}
    for row in position_rows:
        positions_by_hold_id.setdefault(row["cargo_hold_id"], []).append(row)

    cargo_holds = [
        CargoHold(
            hold_code=hold_row["hold_code"],
            hold_type=hold_row["hold_type"],
            max_weight=hold_row["max_weight"],
            balance_arm=hold_row["balance_arm"],
            uld_positions=[
                UldPosition(
                    position_code=p["position_code"],
                    balance_arm=p["balance_arm"],
                    allowed_ulds=p["allowed_ulds"],
                    mutually_exclusive_with=p["mutually_exclusive_with"],
                )
                for p in positions_by_hold_id.get(hold_row["id"], [])
            ],
        )
        for hold_row in cargo_hold_rows
    ]

    return AircraftProfile(envelope=envelope, cabin_zones=cabin_zones, cargo_holds=cargo_holds)
