"""Texto que usa la IA: descripción de la escuela + info adicional que ella cargó.

No entra lo del sistema (intervención, derivación) ni los avances del contratista
(eso vive en comentarios / WhatsApp, no acá).
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from models.reclamo import Reclamo

_MARCAS_EXCLUIDAS = (
    "Pendiente de intervención",
    "[DERIVADO A OPERADOR]",
    "[Sistema]",
    "[CU-05]",
    "[WhatsApp",
    "[IA visión]",
)
_PREFIJO_INFO = re.compile(r"^\[Info adicional [^\]]+\]\s*")


def observaciones_utiles(observaciones: str | None) -> str:
    """Solo notas de la escuela: alta u [Info adicional]. Nada de sistema ni contratista."""
    lineas: list[str] = []
    for cruda in (observaciones or "").splitlines():
        if any(marca in cruda for marca in _MARCAS_EXCLUIDAS):
            continue
        limpia = _PREFIJO_INFO.sub("", cruda).strip()
        if limpia:
            lineas.append(limpia)
    return "\n".join(lineas)


def texto_para_ia(reclamo: Reclamo, db: Session | None = None) -> str:
    """Cuerpo que ven clasificación, duplicados y estimación."""
    del db
    descripcion = (reclamo.descripcion or "").strip()
    extra = observaciones_utiles(reclamo.observaciones)

    bloques = [descripcion] if descripcion else []
    if extra:
        bloques.append(f"Información adicional:\n{extra}")
    return "\n\n".join(bloques).strip()
