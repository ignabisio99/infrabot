"""Configuración operativa (umbrales de auditoría)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.usuario import Usuario
from schemas.configuracion import UmbralesAuditoriaOut, UmbralesAuditoriaUpdate
from services.configuracion_auditoria import obtener_o_crear

router = APIRouter(prefix="/configuracion", tags=["configuracion"])


@router.get("/auditoria", response_model=UmbralesAuditoriaOut)
def obtener_auditoria(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    fila = obtener_o_crear(db)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/auditoria", response_model=UmbralesAuditoriaOut)
def actualizar_auditoria(
    datos: UmbralesAuditoriaUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    fila = obtener_o_crear(db)
    fila.umbral_aprobar = datos.umbral_aprobar
    fila.umbral_revisar = datos.umbral_revisar
    db.commit()
    db.refresh(fila)
    return fila
