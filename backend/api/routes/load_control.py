import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from repositories.aircraft_repository import get_aircraft_profile
from services.calculation_service import run_calculation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/load-control", tags=["load-control"])


class HoldLoadItem(BaseModel):
    uld_type: str
    weight: float


class CalculateRequest(BaseModel):
    registration: str
    take_off_fuel: float = Field(..., ge=0)
    trip_fuel: float = Field(..., ge=0)
    pax_loads: dict[str, dict[str, int] | float] = Field(default_factory=dict)
    hold_loads: dict[str, HoldLoadItem] = Field(default_factory=dict)


class CalculateResponse(BaseModel):
    zfw: float
    tow: float
    ldw: float
    lizfw: float
    mac_zfw: float
    zfw_within_limits: bool
    tow_within_limits: bool
    ldw_within_limits: bool
    within_limits: bool


@router.post("/calculate", response_model=CalculateResponse)
def calculate(payload: CalculateRequest) -> CalculateResponse:
    """Calcula ZFW/TOW/LDW/LIZFW/%MACZFW a partir de combustível, carga nos
    porões e passageiros, para a aeronave identificada por `registration`
    (perfil lido do Supabase).

    Delega o cálculo a `services.calculation_service.run_calculation` — a
    mesma função usada pela assinatura de loadsheet (`/api/v1/loadsheets`),
    para os dois caminhos nunca poderem divergir na matemática. Uma
    violação estrutural de ULD ou trip_fuel > take_off_fuel devolve 422.
    Exceder um limite de peso (ZFW/TOW/LDW) NÃO bloqueia o cálculo — devolve
    os valores reais com as flags `*_within_limits` a false, para o operador
    ver os números mesmo quando estão fora do envelope.
    """
    try:
        profile = get_aircraft_profile(payload.registration)
    except Exception:
        # Erro de infraestrutura (env vars em falta, Supabase indisponível, etc.)
        # — nunca deixar escapar um stack trace/erro cru para o cliente.
        logger.exception("Falha ao ir buscar o perfil da aeronave '%s' ao Supabase", payload.registration)
        raise HTTPException(status_code=503, detail="Serviço de dados de aeronaves indisponível.")

    if profile is None:
        raise HTTPException(status_code=404, detail=f"Aeronave '{payload.registration}' não encontrada.")

    hold_loads = {code: item.model_dump() for code, item in payload.hold_loads.items()}

    try:
        result = run_calculation(profile, payload.take_off_fuel, payload.trip_fuel, payload.pax_loads, hold_loads)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CalculateResponse(
        zfw=result.zfw,
        tow=result.tow,
        ldw=result.ldw,
        lizfw=result.lizfw,
        mac_zfw=result.mac_zfw,
        zfw_within_limits=result.zfw_within_limits,
        tow_within_limits=result.tow_within_limits,
        ldw_within_limits=result.ldw_within_limits,
        within_limits=result.within_limits,
    )
