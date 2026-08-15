from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.dependencies import get_current_user
from models.contratista import Contratista
from models.presupuesto import ItemPresupuesto, Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from schemas.presupuesto import PresupuestoCreate, PresupuestoOut

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


def _validar_referencias(datos: PresupuestoCreate, db: Session):
    if db.get(Reclamo, datos.reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    if db.get(Contratista, datos.contratista_id) is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")


@router.post("", response_model=PresupuestoOut, status_code=201)
def crear_presupuesto(datos: PresupuestoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    _validar_referencias(datos, db)

    nuevo_presupuesto = Presupuesto(
        reclamo_id=datos.reclamo_id,
        contratista_id=datos.contratista_id,
        observaciones=datos.observaciones,
        items=[ItemPresupuesto(**item.model_dump()) for item in datos.items],
    )
    db.add(nuevo_presupuesto)
    db.commit()
    db.refresh(nuevo_presupuesto)
    return nuevo_presupuesto


def _con_relaciones(query):
    return query.options(
        joinedload(Presupuesto.items),
        joinedload(Presupuesto.reclamo),
        joinedload(Presupuesto.contratista),
    )


@router.get("", response_model=list[PresupuestoOut])
def listar_presupuestos(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    return (
        _con_relaciones(db.query(Presupuesto)).order_by(Presupuesto.fecha.desc()).all()
    )


@router.get("/{presupuesto_id}", response_model=PresupuestoOut)
def obtener_presupuesto(presupuesto_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    presupuesto = _con_relaciones(db.query(Presupuesto)).filter(
        Presupuesto.id == presupuesto_id
    ).first()
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    return presupuesto


@router.put("/{presupuesto_id}", response_model=PresupuestoOut)
def actualizar_presupuesto(
    presupuesto_id: int, datos: PresupuestoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)
):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    _validar_referencias(datos, db)

    presupuesto.reclamo_id = datos.reclamo_id
    presupuesto.contratista_id = datos.contratista_id
    presupuesto.observaciones = datos.observaciones
    presupuesto.items = [ItemPresupuesto(**item.model_dump()) for item in datos.items]

    db.commit()
    db.refresh(presupuesto)
    return presupuesto


@router.delete("/{presupuesto_id}", status_code=204)
def eliminar_presupuesto(presupuesto_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    db.delete(presupuesto)
    db.commit()
