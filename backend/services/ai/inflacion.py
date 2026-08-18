"""Inflación IPC (INDEC) vía API Series de Tiempo de datos.gob.ar + cache local."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from core.ai import config
from models.indice_inflacion import IndiceInflacion

logger = logging.getLogger(__name__)


def _periodo(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def sync_indices(db: Session, *, start_date: str | None = None) -> int:
    """Descarga la serie IPC y upserta en indice_inflacion. Devuelve filas tocadas."""
    serie = config.inflacion_serie_id()
    params = {
        "ids": serie,
        "format": "json",
        "limit": 1000,
        "sort": "asc",
        "metadata": "none",
    }
    if start_date:
        params["start_date"] = start_date

    url = config.inflacion_api_url()
    try:
        with httpx.Client(timeout=30.0, verify=config.ai_ssl_verify()) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        logger.exception("No se pudo sincronizar IPC desde %s", url)
        raise

    data = payload.get("data") or []
    tocadas = 0
    for fila in data:
        # Formato típico: [fecha, valor] o dict
        if isinstance(fila, (list, tuple)) and len(fila) >= 2:
            fecha_raw, valor = fila[0], fila[1]
        elif isinstance(fila, dict):
            fecha_raw = fila.get("fecha") or fila.get("date") or fila.get("timestamp")
            valor = fila.get(serie) or fila.get("valor") or fila.get("value")
        else:
            continue
        if fecha_raw is None or valor is None:
            continue
        periodo = str(fecha_raw)[:7]
        try:
            indice = float(valor)
        except (TypeError, ValueError):
            continue

        existente = db.query(IndiceInflacion).filter(IndiceInflacion.periodo == periodo).first()
        if existente:
            existente.indice = indice
            existente.fuente = f"datos.gob.ar:{serie}"
            existente.actualizado_en = datetime.now(timezone.utc)
        else:
            db.add(
                IndiceInflacion(
                    periodo=periodo,
                    indice=indice,
                    fuente=f"datos.gob.ar:{serie}",
                )
            )
        tocadas += 1
    return tocadas


def obtener_indice(db: Session, periodo: str) -> float | None:
    """Busca el índice del período; si no hay exacto, el más cercano anterior."""
    exacto = db.query(IndiceInflacion).filter(IndiceInflacion.periodo == periodo).first()
    if exacto:
        return float(exacto.indice)

    anterior = (
        db.query(IndiceInflacion)
        .filter(IndiceInflacion.periodo <= periodo)
        .order_by(IndiceInflacion.periodo.desc())
        .first()
    )
    if anterior:
        return float(anterior.indice)

    # Último disponible (si pedimos un futuro o cache vacío parcial)
    ultimo = db.query(IndiceInflacion).order_by(IndiceInflacion.periodo.desc()).first()
    return float(ultimo.indice) if ultimo else None


def factor_ajuste(db: Session, fecha_desde: date, fecha_hasta: date | None = None) -> tuple[Decimal, dict]:
    """Factor = indice_hasta / indice_desde. Si faltan datos, retorna 1.0."""
    hasta = fecha_hasta or date.today()
    p_desde = _periodo(fecha_desde)
    p_hasta = _periodo(hasta)

    idx_desde = obtener_indice(db, p_desde)
    idx_hasta = obtener_indice(db, p_hasta)

    meta = {
        "periodo_desde": p_desde,
        "periodo_hasta": p_hasta,
        "indice_desde": idx_desde,
        "indice_hasta": idx_hasta,
        "serie_ipc": config.inflacion_serie_id(),
        "fuente_inflacion": "cache_local",
    }

    if not idx_desde or not idx_hasta or idx_desde <= 0:
        meta["factor"] = 1.0
        meta["aviso"] = "Sin índices suficientes; factor=1"
        return Decimal("1"), meta

    factor = Decimal(str(idx_hasta / idx_desde))
    meta["factor"] = float(factor)
    return factor, meta


def ajustar_monto(db: Session, monto: Decimal, fecha_referencia: date) -> tuple[Decimal, dict]:
    factor, meta = factor_ajuste(db, fecha_referencia)
    ajustado = (Decimal(monto) * factor).quantize(Decimal("0.01"))
    return ajustado, meta
