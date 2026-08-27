from fastapi import APIRouter
from pydantic import BaseModel

from core.models import AircraftProfile

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
