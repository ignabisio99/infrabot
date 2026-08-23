from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.dependencies import get_current_user
from models.contratista import Contratista
from models.presupuesto import ItemPresupuesto, Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from schemas.presupuesto import PresupuestoCreate, PresupuestoOut, PresupuestoUpdate
from services import estados_reclamo

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


def _obtener_reclamo_cotizable(reclamo_id: int, db: Session) -> Reclamo:
    """Devuelve el reclamo sólo si su estado admite que se le carguen presupuestos."""
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    try:
        estados_reclamo.validar_admite_presupuesto(reclamo)
    except estados_reclamo.ReclamoNoAdmitePresupuesto as error:
        raise HTTPException(status_code=409, detail=str(error))

    return reclamo


def _validar_contratista(contratista_id: int, db: Session) -> None:
    if db.get(Contratista, contratista_id) is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")


@router.post("", response_model=PresupuestoOut, status_code=201)
def crear_presupuesto(datos: PresupuestoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = _obtener_reclamo_cotizable(datos.reclamo_id, db)
    _validar_contratista(datos.contratista_id, db)

    nuevo_presupuesto = Presupuesto(
        reclamo_id=datos.reclamo_id,
        contratista_id=datos.contratista_id,
        observaciones=datos.observaciones,
        items=[ItemPresupuesto(**item.model_dump()) for item in datos.items],
    )
    db.add(nuevo_presupuesto)
    # Si es el primero, el reclamo pasa solo a EN_EVALUACION.
    estados_reclamo.sincronizar_por_presupuestos(db, reclamo)
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
    presupuesto_id: int, datos: PresupuestoUpdate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)
):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    # Crear y eliminar sincronizan el estado del reclamo; editar no, porque no cambia
    # qué reclamos tienen presupuestos. El estado igual se mira, para que un expediente
    # que ya eligió contratista no se siga retocando.
    _obtener_reclamo_cotizable(presupuesto.reclamo_id, db)
    _validar_contratista(datos.contratista_id, db)

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

    reclamo = presupuesto.reclamo
    db.delete(presupuesto)
    # Si era el último, el reclamo vuelve a esperar presupuestos.
    estados_reclamo.sincronizar_por_presupuestos(db, reclamo)
    db.commit()
