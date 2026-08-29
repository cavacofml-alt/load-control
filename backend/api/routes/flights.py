import logging

from fastapi import APIRouter, HTTPException

from core.models import Flight
from repositories.flight_repository import get_flight, list_flights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])


@router.get("", response_model=list[Flight])
def get_flights() -> list[Flight]:
    try:
        return list_flights()
    except Exception:
        logger.exception("Falha ao listar voos no Supabase")
        raise HTTPException(status_code=503, detail="Serviço de voos indisponível.")


@router.get("/{flight_id}", response_model=Flight)
def get_flight_detail(flight_id: str) -> Flight:
    try:
        flight = get_flight(flight_id)
    except Exception:
        logger.exception("Falha ao ir buscar o voo '%s' ao Supabase", flight_id)
        raise HTTPException(status_code=503, detail="Serviço de voos indisponível.")

    if flight is None:
        raise HTTPException(status_code=404, detail=f"Voo '{flight_id}' não encontrado.")
    return flight
