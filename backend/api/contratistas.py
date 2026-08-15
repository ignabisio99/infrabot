from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from models.contratista import Contratista
from models.usuario import Usuario
from schemas.contratista import ContratistaCreate, ContratistaOut

router = APIRouter(prefix="/contratistas", tags=["contratistas"])


@router.post("", response_model=ContratistaOut, status_code=201)
def crear_contratista(contratista: ContratistaCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    nuevo_contratista = Contratista(**contratista.model_dump())
    db.add(nuevo_contratista)
    db.commit()
    db.refresh(nuevo_contratista)
    return nuevo_contratista


@router.get("", response_model=list[ContratistaOut])
def listar_contratistas(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    return db.query(Contratista).order_by(Contratista.nombre_empresa).all()


@router.get("/{contratista_id}", response_model=ContratistaOut)
def obtener_contratista(contratista_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    contratista = db.get(Contratista, contratista_id)
    if contratista is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")
    return contratista


@router.put("/{contratista_id}", response_model=ContratistaOut)
def actualizar_contratista(
    contratista_id: int, datos: ContratistaCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)
):
    contratista = db.get(Contratista, contratista_id)
    if contratista is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")
    for campo, valor in datos.model_dump().items():
        setattr(contratista, campo, valor)
    db.commit()
    db.refresh(contratista)
    return contratista


@router.delete("/{contratista_id}", status_code=204)
def eliminar_contratista(contratista_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    contratista = db.get(Contratista, contratista_id)
    if contratista is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")
    db.delete(contratista)
    db.commit()
