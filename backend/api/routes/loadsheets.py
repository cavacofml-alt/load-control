import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.routes.load_control import HoldLoadItem
from core.models import Loadsheet
from repositories.aircraft_repository import get_aircraft_profile
from repositories.flight_repository import get_flight
from repositories.loadsheet_repository import create_loadsheet, list_loadsheets
from services.calculation_service import run_calculation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/loadsheets", tags=["loadsheets"])


class SignLoadsheetRequest(BaseModel):
    flight_id: str
    take_off_fuel: float = Field(..., ge=0)
    trip_fuel: float = Field(..., ge=0)
    pax_loads: dict[str, dict[str, int] | float] = Field(default_factory=dict)
    hold_loads: dict[str, HoldLoadItem] = Field(default_factory=dict)


@router.get("/{flight_id}", response_model=list[Loadsheet])
def get_loadsheet_history(flight_id: str) -> list[Loadsheet]:
    try:
        return list_loadsheets(flight_id)
    except Exception:
        logger.exception("Falha ao listar loadsheets do voo '%s'", flight_id)
        raise HTTPException(status_code=503, detail="Serviço de loadsheets indisponível.")


@router.post("", response_model=Loadsheet)
def sign_loadsheet(payload: SignLoadsheetRequest) -> Loadsheet:
    """Assina (regista de forma imutável) uma loadsheet para um voo.

    Ao contrário de `/api/v1/load-control/calculate` (pré-visualização em
    tempo real, que nunca bloqueia por excesso de peso), esta operação
    BLOQUEIA com 422 se `within_limits` for false — assinar é uma garantia
    de segurança à tripulação de voo, uma operação estrutural diferente de
    uma vista de trabalho editável.

    ATENÇÃO: não existe ainda sistema de autenticação de utilizadores. O
    `signed_by` usa um perfil de demonstração fixo, identificado pela env var
    `DEMO_SIGNER_PROFILE_ID` e controlado pelo BACKEND — nunca aceite do
    cliente, que seria trivialmente falsificável sem autenticação real. Ver
    PROGRESS.md para o plano de substituir isto por autenticação a sério.

    `tow_cg`/`tow_mac` ficam sempre `None` na loadsheet criada — ver
    `services.calculation_service.CalculationResult`.
    """
    signer_id = os.environ.get("DEMO_SIGNER_PROFILE_ID")
    if not signer_id:
        raise HTTPException(status_code=503, detail="DEMO_SIGNER_PROFILE_ID não configurado no backend.")

    try:
        flight = get_flight(payload.flight_id)
    except Exception:
        logger.exception("Falha ao ir buscar o voo '%s' ao Supabase", payload.flight_id)
        raise HTTPException(status_code=503, detail="Serviço de voos indisponível.")

    if flight is None:
        raise HTTPException(status_code=404, detail=f"Voo '{payload.flight_id}' não encontrado.")
    if not flight.aircraft_registration:
        raise HTTPException(status_code=422, detail="Voo sem aeronave atribuída — não é possível calcular a carga.")

    try:
        profile = get_aircraft_profile(flight.aircraft_registration)
    except Exception:
        logger.exception("Falha ao ir buscar o perfil da aeronave '%s' ao Supabase", flight.aircraft_registration)
        raise HTTPException(status_code=503, detail="Serviço de dados de aeronaves indisponível.")

    if profile is None:
        raise HTTPException(status_code=404, detail=f"Aeronave '{flight.aircraft_registration}' não encontrada.")

    hold_loads = {code: item.model_dump() for code, item in payload.hold_loads.items()}

    try:
        result = run_calculation(profile, payload.take_off_fuel, payload.trip_fuel, payload.pax_loads, hold_loads)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result.within_limits:
        raise HTTPException(
            status_code=422,
            detail="Não é possível assinar: um ou mais pesos (ZFW/TOW/LDW) excedem os limites estruturais.",
        )

    try:
        return create_loadsheet(
            flight_id=payload.flight_id,
            result=result,
            raw_payload=payload.model_dump(),
            signed_by=signer_id,
        )
    except Exception:
        logger.exception("Falha ao gravar a loadsheet do voo '%s' no Supabase", payload.flight_id)
        raise HTTPException(status_code=503, detail="Serviço de loadsheets indisponível.")
