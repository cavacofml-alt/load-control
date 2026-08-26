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
