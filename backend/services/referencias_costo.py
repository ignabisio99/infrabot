"""Carga de costos históricos desde CSV."""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from models.referencia_costo import ReferenciaCosto

logger = logging.getLogger(__name__)

_RUTA_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "referencias_costo.csv"
)


def _clave(categoria: str, descripcion: str) -> tuple[str, str]:
    return (categoria.strip().lower(), descripcion.strip().lower())


def _es_de_presupuesto(fuente: str | None) -> bool:
    return (fuente or "").startswith("presupuesto:")


def _es_reemplazable_por_csv(fuente: str | None) -> bool:
    """Filas que salieron de este CSV y se pueden apagar si ya no están en el archivo."""
    valor = fuente or ""
    return (
        valor == "seed_csv"
        or valor.startswith("appmaestro:")
        or valor.startswith("aberturaslyl:")
    )


def _parsear_monto(valor: str | None) -> Decimal | None:
    try:
        monto = Decimal(str(valor or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if monto <= 0:
        return None
    return monto


def _parsear_fecha(valor: str | None) -> date:
    crudo = (valor or "").strip()
    try:
        return date.fromisoformat(crudo) if crudo else date.today()
    except ValueError:
        return date.today()


@dataclass(frozen=True)
class ResultadoCsvReferencias:
    creadas: int
    actualizadas: int
    omitidas: int = 0


def cargar_referencias_si_faltan(db: Session, ruta_csv: str | None = None) -> int:
    """Inserta filas del CSV que no existan ya (misma categoría + descripción).

    No pisa registros existentes. El botón de Configuración usa `sincronizar_desde_csv`.
    """
    return sincronizar_desde_csv(db, ruta_csv, solo_nuevas=True).creadas


def sincronizar_desde_csv(
    db: Session, ruta_csv: str | None = None, *, solo_nuevas: bool = False
) -> ResultadoCsvReferencias:
    """Inserta filas nuevas y, si no es `solo_nuevas`, actualiza las que cambiaron.

    No toca referencias que vinieron de un presupuesto (`fuente=presupuesto:{id}`).
    """
    ruta = ruta_csv or _RUTA_CSV
    if not os.path.exists(ruta):
        logger.warning("CSV de referencias de costo no encontrado en %s", ruta)
        return ResultadoCsvReferencias(0, 0, 0)

    por_clave: dict[tuple[str, str], ReferenciaCosto] = {}
    for ref in db.query(ReferenciaCosto).all():
        por_clave[_clave(ref.categoria, ref.descripcion)] = ref

    creadas = 0
    actualizadas = 0
    omitidas = 0
    claves_csv: set[tuple[str, str]] = set()
    with open(ruta, newline="", encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            categoria = (fila.get("categoria") or "").strip()
            descripcion = (fila.get("descripcion") or "").strip()
            if not categoria or not descripcion:
                continue
            monto = _parsear_monto(fila.get("monto_ars"))
            if monto is None:
                continue
            fecha = _parsear_fecha(fila.get("fecha_referencia"))
            unidad = (fila.get("unidad") or "").strip() or None
            fuente = (fila.get("fuente") or "").strip() or "seed_csv"
            clave = _clave(categoria, descripcion)
            claves_csv.add(clave)
            existente = por_clave.get(clave)
            if existente is None:
                ref = ReferenciaCosto(
                    categoria=categoria,
                    descripcion=descripcion,
                    monto_ars=monto,
                    fecha_referencia=fecha,
                    unidad=unidad,
                    fuente=fuente,
                    activo=True,
                )
                db.add(ref)
                por_clave[clave] = ref
                creadas += 1
                continue
            if solo_nuevas:
                omitidas += 1
                continue
            if _es_de_presupuesto(existente.fuente):
                omitidas += 1
                continue
            cambio = False
            if existente.monto_ars != monto:
                existente.monto_ars = monto
                cambio = True
            if existente.fecha_referencia != fecha:
                existente.fecha_referencia = fecha
                cambio = True
            if (existente.unidad or None) != unidad:
                existente.unidad = unidad
                cambio = True
            if (existente.fuente or None) != fuente:
                existente.fuente = fuente
                cambio = True
            if not existente.activo:
                existente.activo = True
                cambio = True
            if cambio:
                actualizadas += 1
            else:
                omitidas += 1

    if not solo_nuevas:
        for ref in por_clave.values():
            if _es_de_presupuesto(ref.fuente) or not _es_reemplazable_por_csv(ref.fuente):
                continue
            if _clave(ref.categoria, ref.descripcion) in claves_csv or not ref.activo:
                continue
            ref.activo = False
            actualizadas += 1

    return ResultadoCsvReferencias(creadas, actualizadas, omitidas)
