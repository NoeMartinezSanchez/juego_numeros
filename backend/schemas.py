from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str


class ReglaEstado(BaseModel):
    label: str
    cumple: bool


class TicketsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=1, le=50)
    rules: Optional[Dict[str, object]] = None
    seed: Optional[int] = None


class TicketsResponse(BaseModel):
    tickets: List[List[int]]
    reglas: List[List[ReglaEstado]]


class WheelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core: List[int]


class WheelResponse(BaseModel):
    tickets: List[List[int]]
    garantia: bool


class EvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bolsa: float = Field(ge=0, allow_inf_nan=False)
    precio: float = Field(default=15, gt=0, allow_inf_nan=False)
    ganadores: int = Field(default=1, ge=1)
    tickets: int = Field(default=1, ge=1)


class RangoFechas(BaseModel):
    desde: str
    hasta: str


class UltimoSorteo(BaseModel):
    concurso: int
    fecha: str
    bolsa: float


class EstadisticasBolsa(BaseModel):
    min: float
    max: float
    media: float
    mediana: float


class HistoricoResponse(BaseModel):
    total_sorteos: int
    rango_fechas: RangoFechas
    ultimos_sorteos: List[UltimoSorteo]
    streak_actual: int
    periodo_bote_alto: bool
    estadisticas_bolsa: EstadisticasBolsa
