from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel

from models.reclamo import EstadoReclamo, PrioridadReclamo

T = TypeVar("T")


class Comparacion(BaseModel, Generic[T]):
    """El valor del período elegido y el del período de igual largo inmediatamente anterior."""

    actual: T
    anterior: T


class KpisDashboard(BaseModel):
    reclamos_abiertos: int
    pendientes_revision: int
    en_evaluacion: int
    visitas_proximos_7_dias: int
    ingresados: Comparacion[int]
    finalizados: Comparacion[int]
    monto_aprobado: Comparacion[Decimal]
    # Null en un período sin reclamos finalizados: sin casos no hay promedio.
    dias_promedio_resolucion: Comparacion[float | None]


class ConteoPorEstado(BaseModel):
    estado: EstadoReclamo
    cantidad: int


class PuntoSerieMensual(BaseModel):
    mes: str  # "YYYY-MM"
    ingresados: int
    finalizados: int
    monto_aprobado: Decimal


class ReclamoEstancado(BaseModel):
    id: int
    nombre_escuela: str
    estado: EstadoReclamo
    prioridad: PrioridadReclamo
    dias_sin_movimiento: int


class ResumenDashboard(BaseModel):
    # Los días que abarca el período de los KPIs comparativos, tal como se pidió.
    periodo_dias: int
    kpis: KpisDashboard
    por_estado: list[ConteoPorEstado]
    serie_mensual: list[PuntoSerieMensual]
    # Qué estados cuenta `reclamos_abiertos`. Viaja en la respuesta para que el link de
    # la tarjeta filtre por exactamente esos y el frontend no repita la máquina de
    # estados, igual que `estados_posibles` en el modelo de Reclamo.
    estados_abiertos: list[EstadoReclamo]
    estancados: list[ReclamoEstancado]
    # Cuántos estancados hay en total: la lista viene recortada a los más antiguos.
    estancados_total: int
    # A partir de cuántos días sin cambio de estado se listó un reclamo como estancado.
    # Va en la respuesta para que el título de la tarjeta no repita la constante.
    dias_sin_movimiento_umbral: int
    # Las categorías que tienen algún reclamo, sin aplicar filtros: las opciones del
    # selector no tienen que desaparecer al elegir una.
    categorias: list[str]
