import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.calculator import BalanceCalculator
from core.load_service import LoadService
from repositories.aircraft_repository import get_aircraft_profile

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

    Corre `LoadService` (overlap + compatibilidade de ULD) antes de calcular;
    uma violação estrutural de ULD devolve 422. Exceder um limite de peso
    (ZFW/TOW/LDW) NÃO bloqueia o cálculo — devolve os valores reais com as
    flags `*_within_limits` a false, para o operador ver os números mesmo
    quando estão fora do envelope, tal como já acontecia só para o ZFW.
    """
    if payload.trip_fuel > payload.take_off_fuel:
        raise HTTPException(
            status_code=422,
            detail=f"Trip fuel ({payload.trip_fuel}kg) não pode exceder o Take-Off fuel ({payload.take_off_fuel}kg).",
        )

    try:
        profile = get_aircraft_profile(payload.registration)
    except Exception:
        # Erro de infraestrutura (env vars em falta, Supabase indisponível, etc.)
        # — nunca deixar escapar um stack trace/erro cru para o cliente.
        logger.exception("Falha ao ir buscar o perfil da aeronave '%s' ao Supabase", payload.registration)
        raise HTTPException(status_code=503, detail="Serviço de dados de aeronaves indisponível.")

    if profile is None:
        raise HTTPException(status_code=404, detail=f"Aeronave '{payload.registration}' não encontrada.")

    envelope, cargo_holds, cabin_zones = profile.envelope, profile.cargo_holds, profile.cabin_zones
    calculator = BalanceCalculator(envelope)
    service = LoadService(calculator)

    hold_loads = {code: item.model_dump() for code, item in payload.hold_loads.items()}

    try:
        lizfw = service.calculate_validated_lizfw(hold_loads, cargo_holds, payload.pax_loads or None, cabin_zones)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    pax_weight = calculator.calculate_pax_weight(payload.pax_loads) if payload.pax_loads else 0.0
    cargo_weight = sum(item.weight for item in payload.hold_loads.values())
    zfw = envelope.dow + cargo_weight + pax_weight

    cg_zfw = calculator.calculate_cg(total_weight=zfw, total_index=lizfw)
    mac_zfw = calculator.calculate_mac_percentage(cg_zfw)

    tow = calculator.calculate_tow(zfw, payload.take_off_fuel)
    ldw = calculator.calculate_ldw(tow, payload.trip_fuel)

    limits = calculator.check_weight_limits(zfw=zfw, tow=tow, law=ldw)

    return CalculateResponse(
        zfw=zfw,
        tow=tow,
        ldw=ldw,
        lizfw=lizfw,
        mac_zfw=mac_zfw,
        zfw_within_limits=limits["zfw_ok"],
        tow_within_limits=limits["tow_ok"],
        ldw_within_limits=limits["law_ok"],
        within_limits=limits["all_cleared"],
    )
