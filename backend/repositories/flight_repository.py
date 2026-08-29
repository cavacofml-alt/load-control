import os
from functools import lru_cache

from supabase import Client, create_client

from core.models import Flight


@lru_cache
def _client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def _to_flight(row: dict) -> Flight:
    # `aircraft` vem embutido via a foreign key flights.aircraft_id -> aircraft.id
    # (sintaxe de embedding do PostgREST); None se o voo não tiver aeronave atribuída.
    aircraft = row.get("aircraft") or {}
    return Flight(
        id=row["id"],
        flight_number=row["flight_number"],
        origin=row["origin"],
        destination=row["destination"],
        std=row["std"],
        status=row["status"],
        aircraft_registration=aircraft.get("registration"),
    )


def list_flights() -> list[Flight]:
    """Lista todos os voos, ordenados por hora de partida (STD)."""
    client = _client()
    rows = client.table("flights").select("*, aircraft(registration)").order("std").execute().data
    return [_to_flight(row) for row in rows]


def get_flight(flight_id: str) -> Flight | None:
    """Devolve `None` se o voo não existir — quem chama decide (ex.: 404)."""
    client = _client()
    rows = client.table("flights").select("*, aircraft(registration)").eq("id", flight_id).execute().data
    if not rows:
        return None
    return _to_flight(rows[0])
