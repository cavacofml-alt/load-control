"""Semeia o perfil real do TC-JNH (A330-300, THY) no Supabase, usando o
AHM565Parser como fonte única de verdade — os mesmos dados que passam nos
testes unitários, não uma transcrição manual paralela.

Requer as variáveis de ambiente SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY
(a service_role key é necessária para bypassar RLS; isto é um script de
administração, não um fluxo de utilizador autenticado).

Uso: python -m scripts.seed_tcjnh
"""
import os
import sys

import truststore

# Usa o certificate store do próprio SO em vez do bundle do certifi — neste
# ambiente há interceção TLS (proxy/antivírus) que o certifi não reconhece.
truststore.inject_into_ssl()

from supabase import create_client  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.ahm565_parser import AHM565Parser  # noqa: E402


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)

    parser = AHM565Parser("dummy")
    envelope = parser.parse()
    cabin_zones = parser.parse_cabin_zones()
    cargo_holds = parser.parse_cargo_holds()

    airline = client.table("airlines").upsert(
        {"iata_code": "TK", "name": "Turkish Airlines"}, on_conflict="iata_code"
    ).execute().data[0]
    print(f"Airline: {airline['iata_code']} ({airline['id']})")

    aircraft = client.table("aircraft").upsert(
        {
            "airline_id": airline["id"],
            "registration": envelope.registration,
            "type_designator": envelope.type_designator,
            "mzfw": envelope.mzfw,
            "mtow": envelope.mtow,
            "mlaw": envelope.mlaw,
            "dow": envelope.dow,
            "doi": envelope.doi,
            "lemac": envelope.lemac,
            "mac_length": envelope.mac_length,
            "k_constant": envelope.k_constant,
            "c_constant": envelope.c_constant,
            "reference_station": envelope.reference_station,
        },
        on_conflict="registration",
    ).execute().data[0]
    print(f"Aircraft: {aircraft['registration']} ({aircraft['id']})")

    for zone in cabin_zones:
        client.table("cabin_zones").upsert(
            {
                "aircraft_id": aircraft["id"],
                "zone_code": zone.zone_code,
                "max_capacity": zone.max_capacity,
                "balance_arm": zone.balance_arm,
            },
            on_conflict="aircraft_id,zone_code",
        ).execute()
    print(f"Cabin zones: {len(cabin_zones)}")

    total_positions = 0
    for hold in cargo_holds:
        hold_row = client.table("cargo_holds").upsert(
            {
                "aircraft_id": aircraft["id"],
                "hold_code": hold.hold_code,
                "hold_type": hold.hold_type,
                "max_weight": hold.max_weight,
                "balance_arm": hold.balance_arm,
            },
            on_conflict="aircraft_id,hold_code",
        ).execute().data[0]

        for position in hold.uld_positions:
            client.table("uld_positions").upsert(
                {
                    "cargo_hold_id": hold_row["id"],
                    "position_code": position.position_code,
                    "balance_arm": position.balance_arm,
                    "allowed_ulds": position.allowed_ulds,
                    "mutually_exclusive_with": position.mutually_exclusive_with,
                },
                on_conflict="cargo_hold_id,position_code",
            ).execute()
            total_positions += 1

    print(f"Cargo holds: {len(cargo_holds)}")
    print(f"ULD positions: {total_positions}")
    print("Seed concluído.")


if __name__ == "__main__":
    main()
