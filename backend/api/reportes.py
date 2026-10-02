"""Reportes operativos y de gestión. Solo administradores.

- GET /reportes/{tipo}        -> datos del reporte en JSON (para previsualizar en la web)
- GET /reportes/{tipo}/csv    -> descarga el reporte como CSV

tipo ∈ {reclamos, presupuestos}
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.usuario import Usuario
from services import reportes as reportes_svc

router = APIRouter(prefix="/reportes", tags=["reportes"])


def _generar(db: Session, tipo: str, desde: str | None, hasta: str | None, estado: str | None):
    if tipo == "reclamos":
        return reportes_svc.reporte_reclamos(db, desde=desde, hasta=hasta, estado=estado)
    if tipo == "presupuestos":
        return reportes_svc.reporte_presupuestos(db, desde=desde, hasta=hasta)
    if tipo == "metricas":
        return reportes_svc.reporte_metricas(db, desde=desde, hasta=hasta)
    raise HTTPException(status_code=404, detail="Tipo de reporte desconocido")


@router.get("/{tipo}")
def obtener_reporte(
    tipo: str,
    desde: str | None = Query(None, description="YYYY-MM-DD"),
    hasta: str | None = Query(None, description="YYYY-MM-DD"),
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    rep = _generar(db, tipo, desde, hasta, estado)
    return {
        "titulo": rep.titulo,
        "desde": rep.desde.isoformat() if rep.desde else None,
        "hasta": rep.hasta.isoformat() if rep.hasta else None,
        "columnas": rep.columnas,
        "filas": rep.filas,
        "resumen": rep.resumen,
    }


@router.get("/{tipo}/csv")
def descargar_reporte_csv(
    tipo: str,
    desde: str | None = Query(None, description="YYYY-MM-DD"),
    hasta: str | None = Query(None, description="YYYY-MM-DD"),
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    rep = _generar(db, tipo, desde, hasta, estado)
    contenido = reportes_svc.a_csv(rep)
    nombre = f"reporte_{tipo}.csv"
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/{tipo}/pdf")
def descargar_reporte_pdf(
    tipo: str,
    desde: str | None = Query(None, description="YYYY-MM-DD"),
    hasta: str | None = Query(None, description="YYYY-MM-DD"),
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    rep = _generar(db, tipo, desde, hasta, estado)
    contenido = reportes_svc.a_pdf(rep)
    nombre = f"reporte_{tipo}.pdf"
    return StreamingResponse(
        iter([contenido]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
