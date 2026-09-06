from decimal import Decimal

from pydantic import BaseModel

from models.reclamo import EstadoReclamo, PrioridadReclamo


class KpisDashboard(BaseModel):
    reclamos_abiertos: int
    pendientes_revision: int
    en_evaluacion: int
    visitas_proximos_7_dias: int
    monto_aprobado_mes: Decimal
    mes_aprobado: str  # "YYYY-MM"
    # Null mientras no haya ningún reclamo finalizado: sin casos no hay promedio.
    dias_promedio_resolucion: float | None
    nuevos_ultimos_30_dias: int


class ConteoPorEstado(BaseModel):
    estado: EstadoReclamo
    cantidad: int


class PuntoSerieMensual(BaseModel):
    mes: str  # "YYYY-MM"
    ingresados: int
    finalizados: int


class ReclamoEstancado(BaseModel):
    id: int
    nombre_escuela: str
    estado: EstadoReclamo
    prioridad: PrioridadReclamo
    dias_sin_movimiento: int


class ResumenDashboard(BaseModel):
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
