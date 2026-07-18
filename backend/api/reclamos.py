from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from models.reclamo import Reclamo
from schemas.reclamo import ReclamoCreate, ReclamoOut

router = APIRouter(prefix="/reclamos", tags=["reclamos"])


@router.post("/crear", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db)):
    nuevo_reclamo = Reclamo(**reclamo.model_dump())
    db.add(nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
    return nuevo_reclamo


@router.get("", response_model=list[ReclamoOut])
def listar_reclamos(db: Session = Depends(get_db)):
    return db.query(Reclamo).order_by(Reclamo.creado_en.desc()).all()


@router.get("/{reclamo_id}", response_model=ReclamoOut)
def obtener_reclamo(reclamo_id: int, db: Session = Depends(get_db)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return reclamo


@router.put("/{reclamo_id}", response_model=ReclamoOut)
def actualizar_reclamo(reclamo_id: int, datos: ReclamoCreate, db: Session = Depends(get_db)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    for campo, valor in datos.model_dump().items():
        setattr(reclamo, campo, valor)
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.delete("/{reclamo_id}", status_code=204)
def eliminar_reclamo(reclamo_id: int, db: Session = Depends(get_db)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    db.delete(reclamo)
    db.commit()
