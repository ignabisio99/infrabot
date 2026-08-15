from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.dependencies import get_current_user
from core.storage import storage
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from schemas.reclamo import FotoReclamoOut, ReclamoCreate, ReclamoOut

router = APIRouter(prefix="/reclamos", tags=["reclamos"])

TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TIPOS_VIDEO_PERMITIDOS = {"video/mp4", "video/quicktime", "video/webm", "video/3gpp"}
TIPOS_MEDIA_PERMITIDOS = TIPOS_IMAGEN_PERMITIDOS | TIPOS_VIDEO_PERMITIDOS


def _con_fotos(query):
    return query.options(joinedload(Reclamo.fotos))


@router.post("", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    nuevo_reclamo = Reclamo(**reclamo.model_dump())
    db.add(nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
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
    for campo, valor in datos.model_dump().items():
        setattr(reclamo, campo, valor)
    db.commit()
    db.refresh(reclamo)
    return reclamo


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
