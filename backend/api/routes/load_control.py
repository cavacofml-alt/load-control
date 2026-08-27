from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.calculator import BalanceCalculator
from core.load_service import LoadService
from repositories.aircraft_repository import get_aircraft_profile

router = APIRouter(prefix="/api/v1/load-control", tags=["load-control"])


class HoldLoadItem(BaseModel):
    uld_type: str
    weight: float


class CalculateRequest(BaseModel):
    registration: str
    pax_loads: dict[str, dict[str, int] | float] = Field(default_factory=dict)
    hold_loads: dict[str, HoldLoadItem] = Field(default_factory=dict)


class CalculateResponse(BaseModel):
    zfw: float
    lizfw: float
    mac_zfw: float
    zfw_within_limits: bool


@router.post("/calculate", response_model=CalculateResponse)
def calculate(payload: CalculateRequest) -> CalculateResponse:
    """Calcula ZFW/LIZFW/%MACZFW a partir de carga nos porões e passageiros,
    para a aeronave identificada por `registration` (perfil lido do Supabase).

    Corre `LoadService` (overlap + compatibilidade de ULD) antes de calcular;
    qualquer violação estrutural devolve 422 em vez de um resultado inválido.
    """
    profile = get_aircraft_profile(payload.registration)
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
    limits = calculator.check_weight_limits(zfw=zfw, tow=zfw, law=zfw)

    return CalculateResponse(zfw=zfw, lizfw=lizfw, mac_zfw=mac_zfw, zfw_within_limits=limits["zfw_ok"])
