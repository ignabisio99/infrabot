"""Auditoría de presupuestos de contratistas vs estimación (CU-03 / RF05)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from models.presupuesto import Presupuesto
from services.ai.estimacion import ultima_estimacion
from services.ai.prompts import SYSTEM_AUDITORIA_NOTAS, user_auditoria_notas

logger = logging.getLogger(__name__)

# Umbrales CU-03 (configurables a futuro).
UMBRAL_APROBAR = Decimal("0.05")   # < 5%
UMBRAL_REVISAR = Decimal("0.20")   # 5–20%


class RecomendacionAuditoria(str, Enum):
    APROBAR = "APROBAR"
    REVISAR = "REVISAR"
    RECHAZAR = "RECHAZAR"


@dataclass(frozen=True)
class InformeAuditoria:
    presupuesto_id: int
    reclamo_id: int
    total_presupuesto: Decimal
    total_estimacion: Decimal | None
    desvio_absoluto: Decimal | None
    desvio_porcentual: Decimal | None
    recomendacion: RecomendacionAuditoria
    notas_tecnicas: str
    proveedor_notas: str
    sin_estimacion: bool


def auditar_presupuesto(db: Session, presupuesto: Presupuesto) -> InformeAuditoria:
    """Compara el presupuesto del contratista contra la última estimación del reclamo.

    La recomendación es solo sugerencia; no cambia estado ni aprueba nada.
    """
    total_presupuesto = sum(
        (item.cantidad * item.costo_unitario for item in presupuesto.items),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    estimacion = ultima_estimacion(db, presupuesto.reclamo_id)
    if estimacion is None:
        return InformeAuditoria(
            presupuesto_id=presupuesto.id,
            reclamo_id=presupuesto.reclamo_id,
            total_presupuesto=total_presupuesto,
            total_estimacion=None,
            desvio_absoluto=None,
            desvio_porcentual=None,
            recomendacion=RecomendacionAuditoria.REVISAR,
            notas_tecnicas=(
                "No hay estimación preliminar para este reclamo. "
                "Generá una con POST /ai/reclamos/{id}/estimacion antes de auditar."
            ),
            proveedor_notas="n/a",
            sin_estimacion=True,
        )

    total_est = Decimal(estimacion.total).quantize(Decimal("0.01"))
    if total_est <= 0:
        desvio_pct = Decimal("1.00")
        desvio_abs = total_presupuesto
    else:
        desvio_abs = (total_presupuesto - total_est).quantize(Decimal("0.01"))
        desvio_pct = (abs(desvio_abs) / total_est).quantize(Decimal("0.0001"))

    if desvio_pct < UMBRAL_APROBAR:
        recomendacion = RecomendacionAuditoria.APROBAR
    elif desvio_pct <= UMBRAL_REVISAR:
        recomendacion = RecomendacionAuditoria.REVISAR
    else:
        recomendacion = RecomendacionAuditoria.RECHAZAR

    resumen = (
        f"Presupuesto #{presupuesto.id}: ${total_presupuesto}. "
        f"Estimación #{estimacion.id}: ${total_est}. "
        f"Desvío: ${desvio_abs} ({float(desvio_pct) * 100:.2f}%). "
        f"Recomendación calculada: {recomendacion.value}."
    )
    notas, proveedor = _notas_tecnicas(resumen)

    return InformeAuditoria(
        presupuesto_id=presupuesto.id,
        reclamo_id=presupuesto.reclamo_id,
        total_presupuesto=total_presupuesto,
        total_estimacion=total_est,
        desvio_absoluto=desvio_abs,
        desvio_porcentual=desvio_pct,
        recomendacion=recomendacion,
        notas_tecnicas=notas,
        proveedor_notas=proveedor,
        sin_estimacion=False,
    )


def _notas_tecnicas(resumen: str) -> tuple[str, str]:
    provider = get_llm_provider()
    try:
        raw = provider.complete_json(
            system=SYSTEM_AUDITORIA_NOTAS,
            user=user_auditoria_notas(resumen=resumen),
            schema_hint={"task": "auditoria_notas", "notas_tecnicas": ""},
        )
        notas = str(raw.get("notas_tecnicas") or resumen).strip()
        return notas, provider.name
    except Exception:
        logger.exception("No se pudieron generar notas de auditoría vía LLM")
        return resumen, provider.name
