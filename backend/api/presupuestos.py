import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.dependencies import get_current_admin, get_current_contratista, get_current_user
from models.contratista import Contratista
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.presupuesto import ItemPresupuesto, Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from schemas.presupuesto import (
    DecisionPresupuesto,
    HistorialEstadoPresupuestoOut,
    PresupuestoCreate,
    PresupuestoOut,
    PresupuestoUpdate,
)
from services import estados_presupuesto, estados_reclamo
from services.ai.automatico import post_presupuesto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


def _con_relaciones(query):
    return query.options(
        joinedload(Presupuesto.items),
        joinedload(Presupuesto.reclamo),
        joinedload(Presupuesto.contratista),
    )


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


def _ficha_del_contratista(db: Session, usuario: Usuario) -> Contratista:
    ficha = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    if ficha is None:
        raise HTTPException(
            status_code=403,
            detail="Tu cuenta no está vinculada a una ficha de contratista.",
        )
    return ficha


def _exigir_acceso(db: Session, presupuesto: Presupuesto, usuario: Usuario) -> None:
    """El organismo opera sobre cualquier presupuesto; un contratista, sólo sobre el suyo."""
    if usuario.es_admin:
        return
    if presupuesto.contratista_id != _ficha_del_contratista(db, usuario).id:
        raise HTTPException(status_code=403, detail="Este presupuesto no es tuyo")


def _validar_sin_decidir(presupuesto: Presupuesto, accion: str) -> None:
    """Uno ya decidido es parte del expediente: editarlo cambiaría lo que se aprobó o
    rechazó, y darlo de baja borraría el registro."""
    if not estados_presupuesto.esta_vigente(presupuesto):
        raise HTTPException(
            status_code=409,
            detail=f"No se puede {accion} un presupuesto en {presupuesto.estado.value}",
        )


def _validar_contratista(contratista_id: int, db: Session) -> None:
    if db.get(Contratista, contratista_id) is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")


@router.post("", response_model=PresupuestoOut, status_code=201)
def crear_presupuesto(datos: PresupuestoCreate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_contratista)):
    reclamo = _obtener_reclamo_cotizable(datos.reclamo_id, db)
    # Al contratista se le impone su ficha; si no, podría ofertar por otra empresa.
    contratista_id = (
        datos.contratista_id if user.es_admin else _ficha_del_contratista(db, user).id
    )
    _validar_contratista(contratista_id, db)

    nuevo_presupuesto = Presupuesto(
        reclamo_id=datos.reclamo_id,
        contratista_id=contratista_id,
        detalle_tarea=datos.detalle_tarea,
        observaciones=datos.observaciones,
        items=[ItemPresupuesto(**item.model_dump()) for item in datos.items],
        # El default de la columna recién se aplica en el INSERT, y el asiento inicial
        # del historial leería None.
        estado=estados_presupuesto.ESTADO_INICIAL,
    )
    db.add(nuevo_presupuesto)
    estados_presupuesto.registrar_estado_inicial(db, nuevo_presupuesto, usuario_id=user.id)
    estados_reclamo.sincronizar_por_presupuestos(db, reclamo)
    db.commit()
    db.refresh(nuevo_presupuesto)
    post_presupuesto(db, nuevo_presupuesto)
    try:
        db.commit()
    except Exception:
        logger.exception("No se pudo persistir la auditoría automática del presupuesto %s", nuevo_presupuesto.id)
        db.rollback()
    return _con_relaciones(db.query(Presupuesto)).filter(Presupuesto.id == nuevo_presupuesto.id).first()


@router.get("", response_model=list[PresupuestoOut])
def listar_presupuestos(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_admin)):
    return (
        _con_relaciones(db.query(Presupuesto)).order_by(Presupuesto.fecha.desc()).all()
    )


@router.get("/{presupuesto_id}", response_model=PresupuestoOut)
def obtener_presupuesto(presupuesto_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    presupuesto = _con_relaciones(db.query(Presupuesto)).filter(
        Presupuesto.id == presupuesto_id
    ).first()
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    _exigir_acceso(db, presupuesto, user)
    return presupuesto


@router.put("/{presupuesto_id}", response_model=PresupuestoOut)
def actualizar_presupuesto(
    presupuesto_id: int, datos: PresupuestoUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_contratista)
):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    # Crear y eliminar sincronizan el reclamo; editar no, porque no cambia qué
    # presupuestos tiene. El estado se mira igual, para no retocar lo ya adjudicado.
    _exigir_acceso(db, presupuesto, user)
    _validar_sin_decidir(presupuesto, "editar")
    _obtener_reclamo_cotizable(presupuesto.reclamo_id, db)
    _validar_contratista(datos.contratista_id, db)

    presupuesto.contratista_id = datos.contratista_id
    presupuesto.detalle_tarea = datos.detalle_tarea
    presupuesto.observaciones = datos.observaciones
    presupuesto.items = [ItemPresupuesto(**item.model_dump()) for item in datos.items]

    db.commit()
    db.refresh(presupuesto)
    post_presupuesto(db, presupuesto)
    try:
        db.commit()
        db.refresh(presupuesto)
    except Exception:
        logger.exception("No se pudo persistir la auditoría automática del presupuesto %s", presupuesto.id)
        db.rollback()
    return _con_relaciones(db.query(Presupuesto)).filter(Presupuesto.id == presupuesto.id).first()


@router.delete("/{presupuesto_id}", status_code=204)
def eliminar_presupuesto(presupuesto_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_contratista)):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    _exigir_acceso(db, presupuesto, user)
    _validar_sin_decidir(presupuesto, "dar de baja")

    reclamo = presupuesto.reclamo
    db.delete(presupuesto)
    estados_reclamo.sincronizar_por_presupuestos(db, reclamo)
    db.commit()


@router.post("/{presupuesto_id}/estado", response_model=PresupuestoOut)
def decidir_presupuesto(
    presupuesto_id: int,
    datos: DecisionPresupuesto,
    db: Session = Depends(get_db),
    # Admin y no get_current_user: Contratista.usuario_id vincula la ficha con una cuenta,
    # así que si no un contratista se aprueba a sí mismo. Es irreversible.
    user: Usuario = Depends(get_current_admin),
):
    presupuesto = _con_relaciones(db.query(Presupuesto)).filter(
        Presupuesto.id == presupuesto_id
    ).first()
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    try:
        estados_presupuesto.decidir(
            db, presupuesto, datos.estado, motivo=datos.motivo, usuario_id=user.id
        )
    except (
        estados_presupuesto.TransicionInvalida,
        estados_presupuesto.EvaluacionNoAbierta,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error))
    except estados_presupuesto.MotivoRequerido as error:
        raise HTTPException(status_code=422, detail=str(error))

    db.commit()
    db.refresh(presupuesto)
    return presupuesto


@router.get("/{presupuesto_id}/historial", response_model=list[HistorialEstadoPresupuestoOut])
def listar_historial_presupuesto(
    presupuesto_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    _exigir_acceso(db, presupuesto, user)
    return (
        db.query(HistorialEstadoPresupuesto)
        .filter(HistorialEstadoPresupuesto.presupuesto_id == presupuesto_id)
        .order_by(HistorialEstadoPresupuesto.fecha, HistorialEstadoPresupuesto.id)
        .all()
    )
