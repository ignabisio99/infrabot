"""Herramientas (tools) que el agente de IA puede invocar durante su análisis.

Cada herramienta consulta datos REALES de la base (padrón de escuelas, reclamos
similares, costos históricos). El agente decide cuáles usar; acá se definen tanto
el esquema que ve el LLM (formato OpenAI function-calling) como el ejecutor Python.

El objetivo: que el análisis del reclamo esté fundamentado en datos concretos del
sistema, no solo en el texto del usuario. Así el agente "piensa y actúa".
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models.reclamo import EstadoReclamo, Reclamo
from services.ai import historicos

logger = logging.getLogger(__name__)

_ESTADOS_ABIERTOS = (
    EstadoReclamo.PENDIENTE_REVISION,
    EstadoReclamo.PENDIENTE_PRESUPUESTO,
)


# --- Definiciones que ve el LLM (formato OpenAI tools) ---
DEFINICIONES_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_padron_escuela",
            "description": (
                "Verifica si una escuela existe en el padrón oficial del Consejo Escolar "
                "de San Martín y devuelve sus datos (nombre oficial, domicilio, localidad)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre de la escuela a buscar"}
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_reclamos_similares",
            "description": (
                "Busca reclamos ya cargados en la misma escuela que puedan ser el mismo "
                "problema o estar relacionados. Útil para detectar duplicados o recurrencia."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_escuela": {"type": "string"},
                    "descripcion": {"type": "string", "description": "Descripción del problema actual"},
                },
                "required": ["nombre_escuela", "descripcion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_costos_referencia",
            "description": (
                "Busca costos históricos de reparaciones similares (ajustados por inflación) "
                "para fundamentar una estimación de presupuesto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "description": "Categoría del reclamo (ej: Plomería)"},
                    "descripcion": {"type": "string"},
                },
                "required": ["categoria", "descripcion"],
            },
        },
    },
]


def construir_ejecutores(db: Session) -> dict:
    """Devuelve el mapa nombre_tool -> función ejecutable, con la sesión de BD inyectada."""

    def consultar_padron_escuela(nombre: str = "") -> dict:
        from services.instituciones import buscar_instituciones

        coincidencias = buscar_instituciones(db, nombre, limite=3)
        if not coincidencias:
            return {"encontrada": False, "candidatas": []}
        return {
            "encontrada": True,
            "candidatas": [
                {"nombre": i.nombre, "domicilio": i.domicilio, "localidad": i.localidad}
                for i in coincidencias
            ],
        }

    def buscar_reclamos_similares(nombre_escuela: str = "", descripcion: str = "") -> dict:
        tentativo = Reclamo(
            nombre_escuela=nombre_escuela or "",
            ubicacion="",
            categoria="Sin clasificar",
            descripcion=descripcion or "",
        )
        from services.ai import duplicados

        candidatos = duplicados.buscar_duplicados(db, tentativo, limite=3)
        return {
            "cantidad": len(candidatos),
            "similares": [
                {
                    "reclamo_id": c.reclamo_id,
                    "estado": c.estado.value,
                    "descripcion": c.descripcion[:200],
                    "similitud": c.similitud,
                }
                for c in candidatos
            ],
        }

    def buscar_costos_referencia(categoria: str = "", descripcion: str = "") -> dict:
        refs = historicos.buscar_referencias(
            db, categoria=categoria or "Otro", descripcion=descripcion or ""
        )
        return {
            "cantidad": len(refs),
            "referencias": [
                {
                    "descripcion": r.descripcion[:200],
                    "monto_ajustado_ars": float(r.monto_ajustado),
                    "similitud": r.similitud,
                }
                for r in refs
            ],
        }

    return {
        "consultar_padron_escuela": consultar_padron_escuela,
        "buscar_reclamos_similares": buscar_reclamos_similares,
        "buscar_costos_referencia": buscar_costos_referencia,
    }
