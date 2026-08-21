"""Estimación preliminar de costos (CU-02 / RF04) con históricos + inflación."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from models.estimacion_preliminar import EstimacionPreliminar
from models.historial_estado_reclamo import OrigenCambioEstado
from models.reclamo import EstadoReclamo, Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import historicos, registro
from services.ai.prompts import SYSTEM_ESTIMACION, user_estimacion
from services.estados_reclamo import TransicionInvalida, cambiar_estado

logger = logging.getLogger(__name__)

UMBRAL_DESVIO_ESTIMACION = Decimal("0.20")

_SCHEMA = {
    "task": "estimacion",
    "materiales": 0,
    "mano_obra": 0,
    "otros": 0,
    "total": 0,
    "confianza": 0.5,
    "detalle": {},
}


def generar_estimacion(
    db: Session,
    reclamo: Reclamo,
    *,
    transicionar: bool = True,
) -> EstimacionPreliminar:
    """Genera y persiste una estimación preliminar. No hace commit.

    Usa referencias históricas ajustadas por IPC y valida desvío vs promedio (anti-alucinación).
    """
    refs = historicos.buscar_referencias(
        db,
        categoria=reclamo.categoria,
        descripcion=reclamo.descripcion,
    )
    confianza_base = historicos.confianza_por_precedentes(refs)

    contexto_refs = []
    meta_inflacion = {}
    for r in refs:
        contexto_refs.append(
            {
                "id": r.id,
                "descripcion": r.descripcion,
                "monto_ajustado_ars": float(r.monto_ajustado),
                "monto_original_ars": float(r.monto_original),
                "similitud": r.similitud,
                "fecha_referencia": r.fecha_referencia,
            }
        )
        if r.meta_inflacion:
            meta_inflacion = r.meta_inflacion

    provider = get_llm_provider()
    raw = provider.complete_json(
        system=SYSTEM_ESTIMACION,
        user=user_estimacion(
            descripcion=reclamo.descripcion,
            categoria=reclamo.categoria,
            prioridad=reclamo.prioridad.value,
            escuela=reclamo.nombre_escuela,
            referencias=contexto_refs,
            confianza_sugerida=confianza_base,
        ),
        schema_hint=_SCHEMA,
    )

    materiales = _as_decimal(raw.get("materiales"))
    mano_obra = _as_decimal(raw.get("mano_obra"))
    otros = _as_decimal(raw.get("otros"))
    total = _as_decimal(raw.get("total"))

    if total <= 0 and refs:
        promedio = sum((r.monto_ajustado for r in refs), Decimal("0")) / len(refs)
        materiales = (promedio * Decimal("0.40")).quantize(Decimal("0.01"))
        mano_obra = (promedio * Decimal("0.50")).quantize(Decimal("0.01"))
        otros = (promedio * Decimal("0.10")).quantize(Decimal("0.01"))
        total = materiales + mano_obra + otros
    elif total <= 0:
        total = materiales + mano_obra + otros

    try:
        confianza_llm = float(raw.get("confianza", confianza_base))
    except (TypeError, ValueError):
        confianza_llm = confianza_base
    confianza = max(0.0, min(1.0, (confianza_base * 0.6) + (confianza_llm * 0.4)))

    requiere_revision, validacion = _validar_desvio(total, refs)
    if requiere_revision:
        confianza = min(confianza, 0.45)

    detalle_llm = raw.get("detalle") if isinstance(raw.get("detalle"), dict) else {}
    detalle = {
        **detalle_llm,
        "referencias_ids": [r.id for r in refs],
        "referencias": contexto_refs,
        "confianza_por_precedentes": confianza_base,
        "factor_inflacion": meta_inflacion.get("factor"),
        "serie_ipc": meta_inflacion.get("serie_ipc"),
        "fuente_inflacion": meta_inflacion.get("fuente_inflacion"),
        "meta_inflacion": meta_inflacion,
        "validacion": validacion,
    }

    estimacion = EstimacionPreliminar(
        reclamo_id=reclamo.id,
        materiales=materiales,
        mano_obra=mano_obra,
        otros=otros,
        total=total,
        confianza=confianza,
        detalle=json.dumps(detalle, ensure_ascii=False),
        proveedor=provider.name,
        requiere_revision=requiere_revision,
    )
    db.add(estimacion)
    db.flush()

    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.ESTIMACION,
        payload={
            "estimacion_id": estimacion.id,
            "materiales": float(materiales),
            "mano_obra": float(mano_obra),
            "otros": float(otros),
            "total": float(total),
            "validacion": validacion,
        },
        reclamo_id=reclamo.id,
        proveedor=provider.name,
        confianza=confianza,
        requiere_revision=requiere_revision,
    )

    if transicionar and reclamo.estado == EstadoReclamo.PENDIENTE_REVISION:
        try:
            cambiar_estado(
                db,
                reclamo,
                EstadoReclamo.PENDIENTE_PRESUPUESTO,
                motivo="Estimación preliminar generada por el Motor de IA",
                origen=OrigenCambioEstado.AUTOMATICO,
            )
        except TransicionInvalida:
            logger.warning(
                "No se pudo transicionar reclamo %s tras estimación", reclamo.id
            )

    return estimacion


def ultima_estimacion(db: Session, reclamo_id: int) -> EstimacionPreliminar | None:
    return (
        db.query(EstimacionPreliminar)
        .filter(EstimacionPreliminar.reclamo_id == reclamo_id)
        .order_by(EstimacionPreliminar.fecha.desc())
        .first()
    )


def _validar_desvio(total: Decimal, refs) -> tuple[bool, dict]:
    if not refs:
        return True, {
            "requiere_revision": True,
            "motivo": "sin_referencias",
            "umbral": float(UMBRAL_DESVIO_ESTIMACION),
            "desvio": None,
            "promedio_refs": None,
        }

    promedio = sum((r.monto_ajustado for r in refs), Decimal("0")) / len(refs)
    if promedio <= 0:
        return True, {
            "requiere_revision": True,
            "motivo": "promedio_refs_invalido",
            "umbral": float(UMBRAL_DESVIO_ESTIMACION),
            "desvio": None,
            "promedio_refs": float(promedio),
        }

    desvio = abs(total - promedio) / promedio
    requiere = desvio > UMBRAL_DESVIO_ESTIMACION
    return requiere, {
        "requiere_revision": requiere,
        "motivo": "desvio_vs_historicos" if requiere else "ok",
        "umbral": float(UMBRAL_DESVIO_ESTIMACION),
        "desvio": float(desvio.quantize(Decimal("0.0001"))),
        "promedio_refs": float(promedio.quantize(Decimal("0.01"))),
    }


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")
