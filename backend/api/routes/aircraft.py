import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import AircraftEnvelope, AircraftProfile
from repositories.aircraft_repository import get_aircraft_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])


class ProfileValidationResponse(BaseModel):
    status: str
    registration: str


@router.post("/profile", response_model=ProfileValidationResponse)
def validate_profile(profile: AircraftProfile) -> ProfileValidationResponse:
    """Valida um payload contra o esquema `AircraftProfile`/`AircraftEnvelope`.

    Por agora só valida — a gravação no Supabase fica para o passo seguinte
    (ver `scripts/seed_tcjnh.py` para o caminho de escrita já existente).
    """
    return ProfileValidationResponse(status="valid", registration=profile.envelope.registration)


@router.get("/{registration}", response_model=AircraftEnvelope)
def get_envelope(registration: str) -> AircraftEnvelope:
    """Devolve os limites estruturais (MZFW/MTOW/MLAW/DOW/DOI etc.) de uma
    aeronave pela matrícula — usado pelo dashboard para saber contra que
    limites desenhar os gauges, sem hardcodar valores de uma única aeronave.
    """
    try:
        profile = get_aircraft_profile(registration)
    except Exception:
        logger.exception("Falha ao ir buscar o perfil da aeronave '%s' ao Supabase", registration)
        raise HTTPException(status_code=503, detail="Serviço de dados de aeronaves indisponível.")

    if profile is None:
        raise HTTPException(status_code=404, detail=f"Aeronave '{registration}' não encontrada.")
    return profile.envelope
