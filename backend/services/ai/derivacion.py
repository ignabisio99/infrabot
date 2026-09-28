"""Derivación a operador humano (RF10): casos críticos o ambiguos.

Estrategia (Nivel 2): la decisión la toma el LLM evaluando el CONTEXTO, no un regex
de palabras sueltas. Si el LLM no está disponible o falla, se cae a la heurística de
keywords de siempre (fallback seguro que nunca deja pasar un caso crítico obvio).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

UMBRAL_CONFIANZA_DERIVACION = 0.75

_CATEGORIAS_AMBIGUAS = frozenset({"otro", "sin clasificar"})

_KEYWORDS_CRITICAS = (
    "gas",
    "incendio",
    "explos",
    "evacu",
    "peligro",
    "riesgo",
    "inund",
    "cortocircuito",
)

_SCHEMA_DERIVACION = {
    "task": "derivacion",
    "razonamiento": "",
    "derivar": False,
    "motivo": "",
}


@dataclass(frozen=True)
class ResultadoDerivacion:
    derivar: bool
    motivo: str | None
    razonamiento: str = ""


def evaluar_derivacion(
    *,
    descripcion: str,
    categoria: str | None,
    confianza: float | None,
) -> ResultadoDerivacion:
    """Decide si el reclamo debe revisarlo un operador humano.

    1) La confianza baja de la clasificación siempre deriva (chequeo barato, sin LLM).
    2) Si hay proveedor LLM real, evalúa criticidad/ambigüedad con contexto.
    3) Si el LLM no está o falla, cae a la heurística de keywords.
    """
    # La baja confianza de clasificación es un criterio objetivo: no gastamos LLM.
    if confianza is not None and confianza < UMBRAL_CONFIANZA_DERIVACION:
        return ResultadoDerivacion(
            derivar=True,
            motivo=f"confianza de clasificación baja ({confianza:.2f})",
            razonamiento="La clasificación automática no fue lo bastante segura.",
        )

    # Con proveedor real o mock evaluamos por contexto (el mock tiene su propia lógica
    # de contexto). Ante cualquier fallo, caemos a la heurística de keywords.
    try:
        return _evaluar_derivacion_llm(descripcion=descripcion, categoria=categoria)
    except Exception:
        logger.exception("Derivación por LLM falló; se usa la heurística de keywords")

    return _evaluar_derivacion_heuristica(descripcion=descripcion, categoria=categoria)


def _evaluar_derivacion_llm(
    *, descripcion: str, categoria: str | None
) -> ResultadoDerivacion:
    """Le pide al LLM que evalúe si hay riesgo real, considerando el contexto."""
    from core.ai.factory import get_llm_provider
    from services.ai.prompts import SYSTEM_DERIVACION, user_derivacion

    provider = get_llm_provider()
    raw = provider.complete_json(
        system=SYSTEM_DERIVACION,
        user=user_derivacion(descripcion=descripcion, categoria=categoria),
        schema_hint=_SCHEMA_DERIVACION,
    )
    derivar = bool(raw.get("derivar"))
    motivo = str(raw.get("motivo") or "").strip() or None
    razonamiento = str(raw.get("razonamiento") or "").strip()
    return ResultadoDerivacion(derivar=derivar, motivo=motivo, razonamiento=razonamiento)


def _evaluar_derivacion_heuristica(
    *, descripcion: str, categoria: str | None
) -> ResultadoDerivacion:
    """Fallback sin LLM: keywords críticas + categoría ambigua."""
    texto = (descripcion or "").lower()

    for kw in _KEYWORDS_CRITICAS:
        if re.search(rf"\b{re.escape(kw)}", texto):
            return ResultadoDerivacion(
                derivar=True,
                motivo=f"palabra crítica detectada: '{kw}'",
                razonamiento="Heurística: el texto contiene una palabra asociada a riesgo.",
            )

    if (categoria or "").strip().lower() in _CATEGORIAS_AMBIGUAS:
        return ResultadoDerivacion(
            derivar=True,
            motivo=f"categoría ambigua: {categoria}",
            razonamiento="Heurística: la categoría no quedó determinada.",
        )

    return ResultadoDerivacion(derivar=False, motivo=None)
