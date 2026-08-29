"""Semeia voos de demonstração ligados ao TC-JNH/TK já semeados por
`seed_tcjnh.py`, para a lista de voos e assinatura de loadsheet terem algo
real para mostrar.

Idempotente por (airline_id, flight_number, std) — usa esse trio como chave
lógica de upsert (a tabela `flights` não tem uma unique constraint própria
para isto, por isso apagamos e reinserimos os voos com estes flight_numbers
em vez de arriscar duplicados a cada corrida do script).

Requer SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.
Uso: python -m scripts.seed_demo_flight
"""
import os
import sys

import truststore

truststore.inject_into_ssl()

from supabase import create_client  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEMO_FLIGHTS = [
    {"flight_number": "TK1234", "origin": "LTFM", "destination": "LPPT", "std": "2026-09-01T06:30:00+00:00"},
    {"flight_number": "TK1235", "origin": "LPPT", "destination": "LTFM", "std": "2026-09-01T14:15:00+00:00"},
]


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)

    airline = client.table("airlines").select("id").eq("iata_code", "TK").limit(1).execute().data
    if not airline:
        raise RuntimeError("Airline 'TK' não encontrada — corre primeiro python -m scripts.seed_tcjnh")
    airline_id = airline[0]["id"]

    aircraft = client.table("aircraft").select("id").eq("registration", "TC-JNH").limit(1).execute().data
    if not aircraft:
        raise RuntimeError("Aeronave 'TC-JNH' não encontrada — corre primeiro python -m scripts.seed_tcjnh")
    aircraft_id = aircraft[0]["id"]

    flight_numbers = [f["flight_number"] for f in DEMO_FLIGHTS]
    client.table("flights").delete().eq("airline_id", airline_id).in_("flight_number", flight_numbers).execute()

    for flight in DEMO_FLIGHTS:
        row = client.table("flights").insert(
            {
                "airline_id": airline_id,
                "aircraft_id": aircraft_id,
                "flight_number": flight["flight_number"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "std": flight["std"],
                "status": "SCHEDULED",
            }
        ).execute().data[0]
        print(f"Flight: {row['flight_number']} ({row['id']})")

    print("Seed de voos concluído.")


if __name__ == "__main__":
    main()
