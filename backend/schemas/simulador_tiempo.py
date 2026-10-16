"""Esquemas Pydantic para el simulador de tiempo (exclusivo administradores)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class AvanzarTiempoIn(BaseModel):
    horas: float = Field(0.0, ge=0, description="Cantidad de horas a avanzar")
    dias: float = Field(0.0, ge=0, description="Cantidad de días a avanzar")
    hasta_proxima_visita: bool = Field(False, description="Avanzar directo hasta la hora de la próxima visita confirmada")
    horas_despues_visita: float = Field(0.1, description="Margen de horas tras la visita para asegurar el disparo de inicio")


class VisitaSimuladaOut(BaseModel):
    id: int
    reclamo_id: int
    escuela: str
    contratista: str
    contratista_telefono: str | None = None
    creador_telefono: str | None = None
    horario_confirmado: str | None = None
    fecha_visita: str | None = None
    fecha_visita_art: str | None = None
    horas_faltantes: float
    dia_antes_enviado: bool
    mismo_dia_enviado: bool
    pregunta_inicio_enviada: bool


class ReclamoEjecucionSimuladoOut(BaseModel):
    id: int
    escuela: str
    contratista: str | None = None
    contratista_telefono: str | None = None
    creador_telefono: str | None = None
    cantidad_envios: int = 0
    consulto_escuela: bool = False
    proxima_pregunta_art: str | None = None


class MensajeSalienteOut(BaseModel):
    id: str
    fecha: str
    fecha_art: str
    to: str
    tipo: str
    body: str
    botones: list[dict[str, Any]] = []
    secciones: list[dict[str, Any]] = []


class EstadoSimuladorTiempoOut(BaseModel):
    ahora_simulado: str
    ahora_art: str
    offset_segundos: float
    offset_descripcion: str
    es_simulado: bool
    proximas_visitas: list[VisitaSimuladaOut] = []
    reclamos_en_ejecucion: list[ReclamoEjecucionSimuladoOut] = []
    ultimos_mensajes: list[MensajeSalienteOut] = []
    acciones_disparadas: list[str] = []

