"""Derivación a operador humano (RF10): casos críticos o ambiguos."""

from __future__ import annotations

import re
from dataclasses import dataclass

UMBRAL_CONFIANZA_DERIVACION = 0.4

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


@dataclass(frozen=True)
class ResultadoDerivacion:
    derivar: bool
    motivo: str | None


def evaluar_derivacion(
    *,
    descripcion: str,
    categoria: str | None,
    confianza: float | None,
) -> ResultadoDerivacion:
    """Decide si el reclamo debe revisarlo un operador humano.

    Deriva si la clasificación es de baja confianza, la categoría es ambigua
    o la descripción menciona situaciones críticas (gas, incendio, etc.).
    """
    texto = (descripcion or "").lower()

    for kw in _KEYWORDS_CRITICAS:
        if re.search(rf"\b{re.escape(kw)}", texto):
            return ResultadoDerivacion(
                derivar=True,
                motivo=f"palabra crítica detectada: '{kw}'",
            )

    if confianza is not None and confianza < UMBRAL_CONFIANZA_DERIVACION:
        return ResultadoDerivacion(
            derivar=True,
            motivo=f"confianza de clasificación baja ({confianza:.2f})",
        )

    if (categoria or "").strip().lower() in _CATEGORIAS_AMBIGUAS:
        return ResultadoDerivacion(
            derivar=True,
            motivo=f"categoría ambigua: {categoria}",
        )

    return ResultadoDerivacion(derivar=False, motivo=None)
