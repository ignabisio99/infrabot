import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from services.ai.automatico import post_alta_reclamo, post_fotos_reclamo
from core.dependencies import get_current_user
from core.storage import storage
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from models.historial_estado_reclamo import HistorialEstadoReclamo
from schemas.reclamo import (
    CambioEstadoReclamo,
    FotoReclamoOut,
    HistorialEstadoReclamoOut,
    ReclamoCreate,
    ReclamoOut,
)
from services import estados_reclamo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reclamos", tags=["reclamos"])

TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TIPOS_VIDEO_PERMITIDOS = {"video/mp4", "video/quicktime", "video/webm", "video/3gpp"}
TIPOS_MEDIA_PERMITIDOS = TIPOS_IMAGEN_PERMITIDOS | TIPOS_VIDEO_PERMITIDOS


def _con_fotos(query):
    return query.options(joinedload(Reclamo.fotos))


@router.post("", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    nuevo_reclamo = Reclamo(**reclamo.model_dump(), estado=estados_reclamo.ESTADO_INICIAL)
    db.add(nuevo_reclamo)
    estados_reclamo.registrar_estado_inicial(db, nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
    post_alta_reclamo(db, nuevo_reclamo)
    try:
        db.commit()
        db.refresh(nuevo_reclamo)
    except Exception:
        logger.exception("No se pudo persistir la IA automática del reclamo %s", nuevo_reclamo.id)
        db.rollback()
    return nuevo_reclamo


@router.get("", response_model=list[ReclamoOut])
def listar_reclamos(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    return _con_fotos(db.query(Reclamo)).order_by(Reclamo.fecha_creacion.desc()).all()


@router.get("/{reclamo_id}", response_model=ReclamoOut)
def obtener_reclamo(reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return reclamo


@router.put("/{reclamo_id}", response_model=ReclamoOut)
def actualizar_reclamo(reclamo_id: int, datos: ReclamoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    # `estado` no está en ReclamoCreate a propósito: sólo se mueve por
    # POST /reclamos/{id}/estado, que valida la transición y deja historial.
    for campo, valor in datos.model_dump().items():
        setattr(reclamo, campo, valor)
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.post("/{reclamo_id}/estado", response_model=ReclamoOut)
def cambiar_estado_reclamo(
    reclamo_id: int,
    datos: CambioEstadoReclamo,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    try:
        # TODO: validar contra el rol del usuario cuando existan (gestor/contratista).
        estados_reclamo.cambiar_estado(
            db, reclamo, datos.estado, motivo=datos.motivo, usuario_id=user.id
        )
    except estados_reclamo.TransicionInvalida as error:
        raise HTTPException(status_code=409, detail=str(error))
    except estados_reclamo.MotivoRequerido as error:
        raise HTTPException(status_code=422, detail=str(error))

    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.get("/{reclamo_id}/historial", response_model=list[HistorialEstadoReclamoOut])
def listar_historial_reclamo(
    reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)
):
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return (
        db.query(HistorialEstadoReclamo)
        .filter(HistorialEstadoReclamo.reclamo_id == reclamo_id)
        .order_by(HistorialEstadoReclamo.fecha, HistorialEstadoReclamo.id)
        .all()
    )


@router.delete("/{reclamo_id}", status_code=204)
def eliminar_reclamo(reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    tiene_presupuestos = (
        db.query(Presupuesto).filter(Presupuesto.reclamo_id == reclamo_id).first() is not None
    )
    if tiene_presupuestos:
        raise HTTPException(
            status_code=409, detail="No se puede eliminar el reclamo: tiene presupuestos asociados"
        )
    for foto in reclamo.fotos:
        storage.eliminar(foto.url)
    db.delete(reclamo)
    db.commit()


@router.post("/{reclamo_id}/fotos", response_model=FotoReclamoOut, status_code=201)
def subir_foto(reclamo_id: int, archivo: UploadFile = File(...), db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    if archivo.content_type not in TIPOS_MEDIA_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser una imagen (jpg, png, webp) o video (mp4, mov, webm, 3gpp)",
        )

    tipo = TipoMedia.VIDEO if archivo.content_type in TIPOS_VIDEO_PERMITIDOS else TipoMedia.IMAGEN
    url = storage.guardar(archivo, f"reclamos/{reclamo_id}")

    nueva_foto = FotoReclamo(
        reclamo_id=reclamo_id, nombre_archivo=archivo.filename, url=url, tipo=tipo
    )
    db.add(nueva_foto)
    db.commit()
    db.refresh(nueva_foto)
    if tipo == TipoMedia.IMAGEN:
        recargado = (
            _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
        )
        if recargado is not None:
            post_fotos_reclamo(db, recargado)
            try:
                db.commit()
            except Exception:
                logger.exception("No se pudo persistir el análisis de fotos del reclamo %s", reclamo_id)
                db.rollback()
    return nueva_foto


@router.delete("/{reclamo_id}/fotos/{foto_id}", status_code=204)
def eliminar_foto(reclamo_id: int, foto_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    foto = (
        db.query(FotoReclamo)
        .filter(FotoReclamo.id == foto_id, FotoReclamo.reclamo_id == reclamo_id)
        .first()
    )
    if foto is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    storage.eliminar(foto.url)
    db.delete(foto)
    db.commit()
