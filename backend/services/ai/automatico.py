"""Ganchos de IA que corren solos en el flujo (alta de reclamo, fotos, presupuesto).

Si fallan, se loguean y no abortan la operación de negocio.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, joinedload

from models.foto_reclamo import TipoMedia
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import auditoria as auditoria_svc
from services.ai.derivacion import evaluar_derivacion
from services.ai.grafo import ejecutar_pipeline
from services.ai.registro import registrar
from services.ai.vision_reclamo import analizar_media_reclamo

logger = logging.getLogger(__name__)


def post_alta_reclamo(db: Session, reclamo: Reclamo) -> None:
    """Clasifica, busca duplicados, estima y deriva a operador si corresponde."""
    estado: dict = {}
    try:
        estado = ejecutar_pipeline(db, reclamo)
        db.flush()
    except Exception:
        logger.exception("IA automática falló al procesar reclamo %s", reclamo.id)

    try:
        actualizado = db.get(Reclamo, reclamo.id)
        if actualizado is None:
            return
        der = evaluar_derivacion(
            descripcion=actualizado.descripcion,
            categoria=actualizado.categoria,
            confianza=estado.get("confianza"),
        )
        if der.derivar:
            actualizado.requiere_revision = True
            nota = f"[DERIVADO A OPERADOR] {der.motivo}"
            if nota not in (actualizado.observaciones or ""):
                actualizado.observaciones = (
                    f"{actualizado.observaciones}\n{nota}" if actualizado.observaciones else nota
                ).strip()
            registrar(
                db,
                tipo=TipoRecomendacionIA.DERIVACION,
                payload={
                    "motivo": der.motivo,
                    "razonamiento": der.razonamiento,
                    "categoria": actualizado.categoria,
                    "confianza_clasificacion": estado.get("confianza"),
                    "automatico": True,
                },
                reclamo_id=actualizado.id,
                requiere_revision=True,
            )
    except Exception:
        logger.exception("Derivación automática falló en reclamo %s", reclamo.id)


def post_fotos_reclamo(db: Session, reclamo: Reclamo) -> None:
    """Analiza las fotos del reclamo si hay imágenes en disco."""
    try:
        if reclamo.fotos is None:
            reclamo = (
                db.query(Reclamo)
                .options(joinedload(Reclamo.fotos))
                .filter(Reclamo.id == reclamo.id)
                .first()
            )
        if reclamo is None:
            return
        if not any(f.tipo == TipoMedia.IMAGEN for f in (reclamo.fotos or [])):
            return
        resultado = analizar_media_reclamo(db, reclamo)
        if resultado.fotos_analizadas == 0:
            return
        registrar(
            db,
            tipo=TipoRecomendacionIA.VISION,
            payload={
                "hallazgos": resultado.hallazgos,
                "severidad": resultado.severidad,
                "sugerencia_descripcion": resultado.sugerencia_descripcion,
                "fotos_analizadas": resultado.fotos_analizadas,
                "enriquecido": False,
                "automatico": True,
            },
            reclamo_id=reclamo.id,
            proveedor=resultado.proveedor,
        )
    except Exception:
        logger.exception("IA automática falló al analizar fotos del reclamo %s", reclamo.id)


def post_presupuesto(db: Session, presupuesto: Presupuesto) -> None:
    """Audita el presupuesto contra la estimación preliminar."""
    try:
        if not presupuesto.items:
            presupuesto = (
                db.query(Presupuesto)
                .options(joinedload(Presupuesto.items))
                .filter(Presupuesto.id == presupuesto.id)
                .first()
            )
        if presupuesto is None:
            return
        informe = auditoria_svc.auditar_presupuesto(db, presupuesto)
        auditoria_svc.persistir_informe(db, informe)
    except Exception:
        logger.exception("IA automática falló al auditar presupuesto %s", presupuesto.id)
