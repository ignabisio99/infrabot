"""Registro persistente de recomendaciones IA (no hace commit)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models.recomendacion_ia import RecomendacionIA, TipoRecomendacionIA


def registrar(
    db: Session,
    *,
    tipo: TipoRecomendacionIA | str,
    payload: dict[str, Any] | list[Any] | str,
    reclamo_id: int | None = None,
    presupuesto_id: int | None = None,
    proveedor: str | None = None,
    confianza: float | None = None,
    requiere_revision: bool = False,
) -> RecomendacionIA:
    if isinstance(tipo, str):
        tipo = TipoRecomendacionIA(tipo)
    if not isinstance(payload, str):
        payload_str = json.dumps(payload, ensure_ascii=False, default=str)
    else:
        payload_str = payload

    evento = RecomendacionIA(
        tipo=tipo,
        reclamo_id=reclamo_id,
        presupuesto_id=presupuesto_id,
        proveedor=proveedor,
        confianza=confianza,
        payload=payload_str,
        requiere_revision=requiere_revision,
    )
    db.add(evento)
    return evento
