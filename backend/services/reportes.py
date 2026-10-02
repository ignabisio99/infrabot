"""Generación de reportes operativos y de gestión (RF: Generación de reportes).

Arma reportes de reclamos y de presupuestos con filtro por rango de fechas, devolviendo
datos estructurados (para previsualizar en la web) y permitiendo exportarlos a CSV.
Los cortes de fecha se hacen en hora local (UTC-3), igual que el dashboard.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo

ART = ZoneInfo("America/Argentina/Buenos_Aires")


@dataclass
class Reporte:
    titulo: str
    desde: datetime | None
    hasta: datetime | None
    columnas: list[str]
    filas: list[list]
    resumen: dict = field(default_factory=dict)


def _rango(desde: str | None, hasta: str | None) -> tuple[datetime | None, datetime | None]:
    """Parsea 'YYYY-MM-DD' a datetimes en hora local. `hasta` incluye todo el día."""
    d = None
    h = None
    if desde:
        d = datetime.strptime(desde, "%Y-%m-%d").replace(tzinfo=ART)
    if hasta:
        h = datetime.strptime(hasta, "%Y-%m-%d").replace(tzinfo=ART) + timedelta(days=1)
    return d, h


def reporte_reclamos(
    db: Session,
    *,
    desde: str | None = None,
    hasta: str | None = None,
    estado: str | None = None,
) -> Reporte:
    """Listado de reclamos del período, con resumen por estado, categoría y prioridad."""
    d, h = _rango(desde, hasta)
    q = db.query(Reclamo)
    if d is not None:
        q = q.filter(Reclamo.fecha_creacion >= d)
    if h is not None:
        q = q.filter(Reclamo.fecha_creacion < h)
    if estado:
        try:
            q = q.filter(Reclamo.estado == EstadoReclamo(estado))
        except ValueError:
            pass
    reclamos = q.order_by(Reclamo.fecha_creacion.desc()).all()

    columnas = ["ID", "Escuela", "Ubicación", "Categoría", "Prioridad", "Estado", "Fecha"]
    filas = [
        [
            r.id,
            r.nombre_escuela,
            r.ubicacion,
            r.categoria,
            r.prioridad.value,
            r.estado.value,
            r.fecha_creacion.astimezone(ART).strftime("%d/%m/%Y %H:%M"),
        ]
        for r in reclamos
    ]

    resumen = {
        "total": len(reclamos),
        "por_estado": dict(Counter(r.estado.value for r in reclamos)),
        "por_categoria": dict(Counter(r.categoria for r in reclamos)),
        "por_prioridad": dict(Counter(r.prioridad.value for r in reclamos)),
    }
    return Reporte(
        titulo="Reporte de reclamos",
        desde=d,
        hasta=h,
        columnas=columnas,
        filas=filas,
        resumen=resumen,
    )


def reporte_presupuestos(
    db: Session,
    *,
    desde: str | None = None,
    hasta: str | None = None,
) -> Reporte:
    """Listado de presupuestos del período, con monto total y desglose por estado."""
    d, h = _rango(desde, hasta)
    q = db.query(Presupuesto).options(
        joinedload(Presupuesto.reclamo),
        joinedload(Presupuesto.contratista),
        joinedload(Presupuesto.items),
    )
    if d is not None:
        q = q.filter(Presupuesto.fecha >= d)
    if h is not None:
        q = q.filter(Presupuesto.fecha < h)
    presupuestos = q.order_by(Presupuesto.fecha.desc()).all()

    columnas = ["ID", "Reclamo", "Escuela", "Contratista", "Monto (ARS)", "Estado", "Fecha"]
    filas = []
    monto_total = 0.0
    monto_aprobado = 0.0
    for p in presupuestos:
        monto = float(sum((i.cantidad * i.costo_unitario for i in p.items), 0))
        monto_total += monto
        if p.estado == EstadoPresupuesto.APROBADO:
            monto_aprobado += monto
        filas.append(
            [
                p.id,
                p.reclamo_id,
                p.reclamo.nombre_escuela if p.reclamo else "—",
                p.contratista.nombre_empresa if p.contratista else "—",
                round(monto, 2),
                p.estado.value,
                p.fecha.astimezone(ART).strftime("%d/%m/%Y %H:%M"),
            ]
        )

    resumen = {
        "total": len(presupuestos),
        "monto_total": round(monto_total, 2),
        "monto_aprobado": round(monto_aprobado, 2),
        "por_estado": dict(Counter(p.estado.value for p in presupuestos)),
    }
    return Reporte(
        titulo="Reporte de presupuestos",
        desde=d,
        hasta=h,
        columnas=columnas,
        filas=filas,
        resumen=resumen,
    )


def reporte_metricas(
    db: Session,
    *,
    desde: str | None = None,
    hasta: str | None = None,
) -> Reporte:
    """Métricas de gestión del período: indicadores agregados (no un listado).

    Pensado para exportar KPIs: cuántos reclamos ingresaron/finalizaron, tasa de
    resolución, días promedio, montos presupuestados/aprobados y desgloses. Si no se
    pasa rango, toma todo el histórico.
    """
    from sqlalchemy import func

    d, h = _rango(desde, hasta)

    # --- Reclamos del período ---
    q_rec = db.query(Reclamo)
    if d is not None:
        q_rec = q_rec.filter(Reclamo.fecha_creacion >= d)
    if h is not None:
        q_rec = q_rec.filter(Reclamo.fecha_creacion < h)
    reclamos = q_rec.all()
    total_rec = len(reclamos)
    por_estado = Counter(r.estado.value for r in reclamos)
    por_categoria = Counter(r.categoria for r in reclamos)
    por_prioridad = Counter(r.prioridad.value for r in reclamos)
    finalizados = por_estado.get(EstadoReclamo.FINALIZADO.value, 0)
    tasa_resolucion = round(finalizados / total_rec * 100, 1) if total_rec else 0.0

    # --- Días promedio de resolución (reclamos finalizados del período) ---
    from models.historial_estado_reclamo import HistorialEstadoReclamo

    finalizacion = (
        db.query(
            HistorialEstadoReclamo.reclamo_id.label("reclamo_id"),
            func.max(HistorialEstadoReclamo.fecha).label("fecha"),
        )
        .filter(HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO)
        .group_by(HistorialEstadoReclamo.reclamo_id)
        .subquery()
    )
    segundos = (
        db.query(func.avg(func.extract("epoch", finalizacion.c.fecha - Reclamo.fecha_creacion)))
        .join(finalizacion, finalizacion.c.reclamo_id == Reclamo.id)
        .scalar()
    )
    dias_promedio = round(float(segundos) / 86400, 1) if segundos is not None else None

    # --- Presupuestos del período ---
    q_pre = db.query(Presupuesto).options(joinedload(Presupuesto.items))
    if d is not None:
        q_pre = q_pre.filter(Presupuesto.fecha >= d)
    if h is not None:
        q_pre = q_pre.filter(Presupuesto.fecha < h)
    presupuestos = q_pre.all()
    monto_total = 0.0
    monto_aprobado = 0.0
    for p in presupuestos:
        monto = float(sum((i.cantidad * i.costo_unitario for i in p.items), 0))
        monto_total += monto
        if p.estado == EstadoPresupuesto.APROBADO:
            monto_aprobado += monto

    # El reporte de métricas es clave-valor: una métrica por fila.
    columnas = ["Métrica", "Valor"]
    filas = [
        ["Reclamos ingresados", total_rec],
        ["Reclamos finalizados", finalizados],
        ["Tasa de resolución (%)", tasa_resolucion],
        ["Días promedio de resolución", dias_promedio if dias_promedio is not None else "—"],
        ["Presupuestos cargados", len(presupuestos)],
        ["Monto total presupuestado (ARS)", round(monto_total, 2)],
        ["Monto aprobado (ARS)", round(monto_aprobado, 2)],
    ]
    # Desgloses como filas adicionales (categoría/prioridad/estado).
    for categoria, cant in sorted(por_categoria.items()):
        filas.append([f"Reclamos por categoría — {categoria}", cant])
    for prioridad, cant in sorted(por_prioridad.items()):
        filas.append([f"Reclamos por prioridad — {prioridad}", cant])
    for estado, cant in sorted(por_estado.items()):
        filas.append([f"Reclamos por estado — {estado}", cant])

    resumen = {
        "total": total_rec,
        "finalizados": finalizados,
        "tasa_resolucion": tasa_resolucion,
        "dias_promedio_resolucion": dias_promedio,
        "monto_total": round(monto_total, 2),
        "monto_aprobado": round(monto_aprobado, 2),
        "por_estado": dict(por_estado),
        "por_categoria": dict(por_categoria),
        "por_prioridad": dict(por_prioridad),
    }
    return Reporte(
        titulo="Métricas de gestión",
        desde=d,
        hasta=h,
        columnas=columnas,
        filas=filas,
        resumen=resumen,
    )


def a_csv(reporte: Reporte) -> str:
    """Serializa un reporte a CSV (encabezado + filas). Abre en Excel/LibreOffice."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(reporte.columnas)
    for fila in reporte.filas:
        writer.writerow(fila)
    return buffer.getvalue()


def _periodo_texto(reporte: Reporte) -> str:
    if reporte.desde and reporte.hasta:
        # `hasta` interno es exclusivo (día +1); se muestra el día real pedido.
        fin = reporte.hasta - timedelta(days=1)
        return f"Período: {reporte.desde.strftime('%d/%m/%Y')} a {fin.strftime('%d/%m/%Y')}"
    if reporte.desde:
        return f"Desde: {reporte.desde.strftime('%d/%m/%Y')}"
    if reporte.hasta:
        fin = reporte.hasta - timedelta(days=1)
        return f"Hasta: {fin.strftime('%d/%m/%Y')}"
    return "Período: histórico completo"


def a_pdf(reporte: Reporte) -> bytes:
    """Genera un PDF con título, período, resumen y la tabla del reporte.

    Usa fpdf2 (puro Python, sin dependencias del sistema). Devuelve los bytes del PDF.
    """
    from fpdf import FPDF

    pdf = FPDF(orientation="L", unit="mm", format="A4")  # horizontal: tablas anchas
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Encabezado
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _latin(reporte.titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, _latin(_periodo_texto(reporte)), new_x="LMARGIN", new_y="NEXT")
    emitido = datetime.now(ART).strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 6, _latin(f"Emitido: {emitido} - InfraBot"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    ancho_util = pdf.w - pdf.l_margin - pdf.r_margin

    # Resumen (si hay)
    if reporte.resumen:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Resumen", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for clave, valor in reporte.resumen.items():
            if isinstance(valor, dict):
                detalle = ", ".join(f"{k}: {v}" for k, v in valor.items())
                texto = f"- {clave.replace('_', ' ')}: {detalle}"
            else:
                texto = f"- {clave.replace('_', ' ')}: {valor}"
            pdf.multi_cell(ancho_util, 5, _latin(texto), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # Tabla
    ancho_col = ancho_util / max(1, len(reporte.columnas))

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for col in reporte.columnas:
        pdf.cell(ancho_col, 7, _latin(str(col)), border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for fila in reporte.filas:
        for celda in fila:
            texto = _latin(str(celda))
            # Recortar textos largos para que no desborden la celda.
            if len(texto) > 40:
                texto = texto[:37] + "..."
            pdf.cell(ancho_col, 6, texto, border=1)
        pdf.ln()

    salida = pdf.output()
    return bytes(salida)


def _latin(texto: str) -> str:
    """Las fuentes core de fpdf2 son latin-1. Reemplaza lo que no entra para no romper."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")
