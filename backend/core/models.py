from typing import Literal

from pydantic import BaseModel, Field


class AircraftEnvelope(BaseModel):
    registration: str = Field(..., max_length=10)
    type_designator: str = Field(..., max_length=10)

    # Limites Estruturais (kg)
    mzfw: float = Field(..., gt=0, description="Maximum Zero Fuel Weight")
    mtow: float = Field(..., gt=0, description="Maximum Take-Off Weight")
    mlaw: float = Field(..., gt=0, description="Maximum Landing Weight")

    # Dados Operacionais Base
    dow: float = Field(..., gt=0, description="Dry Operating Weight")
    doi: float = Field(..., description="Dry Operating Index")

    # Constantes de Cálculo de MAC (Mean Aerodynamic Chord)
    lemac: float = Field(..., description="Leading Edge of MAC")
    mac_length: float = Field(..., gt=0, description="Length of MAC")
    k_constant: float = Field(..., description="K Constant for Index Calculation")
    c_constant: float = Field(..., description="C Constant for Index Calculation")

    # Constantes de Cálculo de MAC e Datum
    reference_station: float = Field(..., description="Reference Station (Datum)")


class CabinZone(BaseModel):
    zone_code: str = Field(..., max_length=2)
    max_capacity: int = Field(..., gt=0)
    balance_arm: float


class UldPosition(BaseModel):
    """Posição física de ULD dentro de um porão. Várias posições podem
    partilhar o mesmo espaço físico (ex.: duas laterais vs. uma central de
    largura total) — `mutually_exclusive_with` regista essa exclusão.

    `allowed_ulds` mapeia tipo de ULD (ex. "AKE", "PMC") -> peso máximo
    estrutural específico desse tipo nesta posição, em vez de um único limite
    genérico — posições partilhadas como as "P" aceitam mais que um tipo,
    cada um com o seu próprio limite (ex.: PAG 4626kg vs. PMC 5103kg)."""

    position_code: str = Field(..., max_length=10)
    balance_arm: float
    allowed_ulds: dict[str, float] = Field(..., description="Tipo de ULD -> peso máximo estrutural (kg)")
    mutually_exclusive_with: list[str] = Field(default_factory=list)


class CargoHold(BaseModel):
    hold_code: str = Field(..., max_length=10)
    hold_type: Literal["LOWER", "MAIN"]
    max_weight: float = Field(..., gt=0)
    balance_arm: float
    uld_positions: list[UldPosition] = Field(default_factory=list)


class AircraftProfile(BaseModel):
    """Fonte de verdade interna da aplicação, independente do formato de origem
    (AHM 560 telex, AHM 565 estruturado, ou outros formatos proprietários)."""

    envelope: AircraftEnvelope
    cabin_zones: list[CabinZone] = Field(default_factory=list)
    cargo_holds: list[CargoHold] = Field(default_factory=list)
