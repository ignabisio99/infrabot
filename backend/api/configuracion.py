"""Configuración operativa (umbrales de auditoría)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.usuario import Usuario
from schemas.configuracion import (
    ConfiguracionAtencionOut,
    ConfiguracionAtencionUpdate,
    UmbralesAuditoriaOut,
    UmbralesAuditoriaUpdate,
)
from services.configuracion_atencion import obtener_o_crear as obtener_atencion
from services.configuracion_atencion import validar_hora
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


@router.get("/atencion", response_model=ConfiguracionAtencionOut)
def obtener_config_atencion(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    fila = obtener_atencion(db)
    db.commit()
    db.refresh(fila)
    return fila


@router.put("/atencion", response_model=ConfiguracionAtencionOut)
def actualizar_config_atencion(
    datos: ConfiguracionAtencionUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    try:
        desde = validar_hora(datos.hora_desde)
        hasta = validar_hora(datos.hora_hasta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fila = obtener_atencion(db)
    fila.dias = datos.dias
    fila.hora_desde = desde
    fila.hora_hasta = hasta
    fila.mensaje_fuera_horario = datos.mensaje_fuera_horario.strip()
    fila.inactividad_usuario_min = datos.inactividad_usuario_min
    db.commit()
    db.refresh(fila)
    return fila
