"""Auditoría de presupuestos de contratistas vs estimación (CU-03 / RF05)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from models.presupuesto import Presupuesto
from services.ai.estimacion import sirve_como_ancla_auditoria, ultima_estimacion
from services.ai.prompts import SYSTEM_AUDITORIA_NOTAS, user_auditoria_notas
from services.configuracion_auditoria import (
    UMBRAL_APROBAR_DEFAULT,
    UMBRAL_REVISAR_DEFAULT,
    obtener_umbrales,
)

logger = logging.getLogger(__name__)

# Fallback si todavía no hay fila en DB (misma idea que el seed).
UMBRAL_APROBAR = UMBRAL_APROBAR_DEFAULT
UMBRAL_REVISAR = UMBRAL_REVISAR_DEFAULT


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
    sin_precedentes: bool = False


def auditar_presupuesto(db: Session, presupuesto: Presupuesto) -> InformeAuditoria:
    """Compara el presupuesto del contratista contra la última estimación del reclamo.

    La recomendación es solo sugerencia; no cambia estado ni aprueba nada.
    """
    total_presupuesto = sum(
        (item.cantidad * item.costo_unitario for item in presupuesto.items),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    estimacion = ultima_estimacion(db, presupuesto.reclamo_id)
    if estimacion is None or not sirve_como_ancla_auditoria(estimacion):
        sin_precedentes = estimacion is not None
        notas = (
            "No hay precedentes históricos para anclar la estimación "
            "(confianza 0 o total $0). No se compara el presupuesto contra esa cifra. "
            "Revisar con criterio técnico."
            if sin_precedentes
            else (
                "No hay estimación preliminar para este reclamo. "
                "Se genera sola al dar de alta el reclamo; si falta, regenerala desde el detalle."
            )
        )
        return InformeAuditoria(
            presupuesto_id=presupuesto.id,
            reclamo_id=presupuesto.reclamo_id,
            total_presupuesto=total_presupuesto,
            total_estimacion=(
                Decimal(estimacion.total).quantize(Decimal("0.01")) if estimacion is not None else None
            ),
            desvio_absoluto=None,
            desvio_porcentual=None,
            recomendacion=RecomendacionAuditoria.REVISAR,
            notas_tecnicas=notas,
            proveedor_notas="n/a",
            sin_estimacion=estimacion is None,
            sin_precedentes=sin_precedentes,
        )

    total_est = Decimal(estimacion.total).quantize(Decimal("0.01"))
    umbral_aprobar, umbral_revisar = obtener_umbrales(db)
    recomendacion, desvio_abs, desvio_pct = _recomendacion_por_desvio(
        total_presupuesto, total_est, umbral_aprobar, umbral_revisar
    )

    if desvio_abs <= 0:
        sentido = "El presupuesto es igual o más barato que la estimación: es favorable."
    else:
        sentido = "El presupuesto es más caro que la estimación."
    resumen = (
        f"Presupuesto #{presupuesto.id}: ${total_presupuesto}. "
        f"Estimación #{estimacion.id}: ${total_est}. "
        f"Desvío: ${desvio_abs} ({float(desvio_pct) * 100:.2f}%). "
        f"{sentido} Recomendación calculada: {recomendacion.value}."
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
        sin_precedentes=False,
    )


def _recomendacion_por_desvio(
    total_presupuesto: Decimal,
    total_est: Decimal,
    umbral_aprobar: Decimal,
    umbral_revisar: Decimal,
) -> tuple[RecomendacionAuditoria, Decimal, Decimal]:
    """Solo penaliza si el presupuesto es más caro. Más barato o igual → APROBAR."""
    desvio_abs = (total_presupuesto - total_est).quantize(Decimal("0.01"))
    desvio_pct = (desvio_abs / total_est).quantize(Decimal("0.0001"))
    if desvio_abs <= 0:
        return RecomendacionAuditoria.APROBAR, desvio_abs, desvio_pct
    if desvio_pct < umbral_aprobar:
        return RecomendacionAuditoria.APROBAR, desvio_abs, desvio_pct
    if desvio_pct <= umbral_revisar:
        return RecomendacionAuditoria.REVISAR, desvio_abs, desvio_pct
    return RecomendacionAuditoria.RECHAZAR, desvio_abs, desvio_pct


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


def persistir_informe(db: Session, informe: InformeAuditoria):
    """Guarda la auditoría en recomendacion_ia (sin commit)."""
    from models.recomendacion_ia import TipoRecomendacionIA
    from services.ai import registro

    requiere = informe.recomendacion.value in ("REVISAR", "RECHAZAR") or informe.sin_estimacion
    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.AUDITORIA,
        payload={
            "recomendacion": informe.recomendacion.value,
            "total_presupuesto": float(informe.total_presupuesto),
            "total_estimacion": float(informe.total_estimacion)
            if informe.total_estimacion is not None
            else None,
            "desvio_absoluto": float(informe.desvio_absoluto)
            if informe.desvio_absoluto is not None
            else None,
            "desvio_porcentual": float(informe.desvio_porcentual)
            if informe.desvio_porcentual is not None
            else None,
            "notas_tecnicas": informe.notas_tecnicas,
            "sin_estimacion": informe.sin_estimacion,
            "sin_precedentes": informe.sin_precedentes,
        },
        reclamo_id=informe.reclamo_id,
        presupuesto_id=informe.presupuesto_id,
        proveedor=informe.proveedor_notas,
        requiere_revision=requiere,
    )
    return informe
