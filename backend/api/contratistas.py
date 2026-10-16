import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin, get_current_user
from models.contratista import Contratista
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import Usuario
from schemas.contratista import ContratistaCreate, ContratistaOut, MiSolicitudOut
from schemas.presupuesto import PresupuestoOut
from services import estados_presupuesto

router = APIRouter(prefix="/contratistas", tags=["contratistas"])


def _solo_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def _vincular_ficha_por_datos(db: Session, usuario: Usuario) -> Contratista | None:
    """Busca una ficha de Contratista que coincida con el usuario (por teléfono) y la vincula.

    Se usa como fallback cuando un usuario contratista todavía no tiene ficha asociada.
    El match es por los últimos dígitos del teléfono para tolerar diferencias de formato.
    """
    tel_usuario = _solo_digitos(usuario.telefono)
    if not tel_usuario:
        return None

    candidatos = db.query(Contratista).filter(Contratista.usuario_id.is_(None)).all()
    for c in candidatos:
        tel_c = _solo_digitos(c.telefono)
        # Compara los últimos 8 dígitos (número local) para tolerar prefijos/formatos
        if tel_c and tel_c[-8:] == tel_usuario[-8:]:
            c.usuario_id = usuario.id
            db.commit()
            db.refresh(c)
            return c
    return None


def _ficha_del_usuario(db: Session, usuario: Usuario) -> Contratista:
    """Resuelve la ficha de Contratista del usuario logueado (o 404)."""
    ficha = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    if ficha is None:
        ficha = _vincular_ficha_por_datos(db, usuario)
    if ficha is None:
        raise HTTPException(
            status_code=404,
            detail="Tu cuenta no está vinculada a una ficha de contratista. Contactá a un administrador.",
        )
    return ficha


@router.get("/mi-ficha", response_model=ContratistaOut)
def obtener_mi_ficha(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Devuelve la ficha de Contratista vinculada al usuario logueado.

    Si no está vinculada, intenta vincularla automáticamente por teléfono.
    """
    return _ficha_del_usuario(db, usuario)


@router.get("/mis-solicitudes", response_model=list[MiSolicitudOut])
def listar_mis_solicitudes(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Reclamos donde el contratista logueado fue convocado a presupuestar."""
    ficha = _ficha_del_usuario(db, usuario)

    solicitudes = (
        db.query(SolicitudPresupuesto)
        .filter(SolicitudPresupuesto.contratista_id == ficha.id)
        .order_by(SolicitudPresupuesto.fecha_solicitud.desc())
        .all()
    )

    # Presupuestos que este contratista cargó, indexados por reclamo
    # Ordenados por id para que, si cargó más de uno, quede el último.
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.contratista_id == ficha.id)
        .order_by(Presupuesto.id)
        .all()
    )
    presupuesto_por_reclamo = {p.reclamo_id: p for p in presupuestos}

    resultado = []
    for s in solicitudes:
        reclamo = db.get(Reclamo, s.reclamo_id)
        if reclamo is None:
            continue
        presupuesto = presupuesto_por_reclamo.get(s.reclamo_id)
        resultado.append(
            MiSolicitudOut(
                reclamo_id=reclamo.id,
                nombre_escuela=reclamo.nombre_escuela,
                ubicacion=reclamo.ubicacion,
                categoria=reclamo.categoria,
                prioridad=reclamo.prioridad.value,
                estado_reclamo=reclamo.estado.value,
                fecha_solicitud=s.fecha_solicitud,
                presupuesto_cargado=presupuesto is not None,
                presupuesto_id=presupuesto.id if presupuesto else None,
                presupuesto_estado=presupuesto.estado.value if presupuesto else None,
                version=presupuesto.version if presupuesto else 0,
                puede_editar=presupuesto is not None and presupuesto.editable,
                puede_ofertar=estados_presupuesto.puede_ofertar(reclamo, ficha.id),
            )
        )
    return resultado


@router.get("/mis-presupuestos", response_model=list[PresupuestoOut])
def listar_mis_presupuestos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Presupuestos cargados por el contratista logueado."""
    from sqlalchemy.orm import joinedload

    ficha = _ficha_del_usuario(db, usuario)
    return (
        db.query(Presupuesto)
        .options(
            joinedload(Presupuesto.items),
            joinedload(Presupuesto.reclamo),
            joinedload(Presupuesto.contratista),
        )
        .filter(Presupuesto.contratista_id == ficha.id)
        .order_by(Presupuesto.fecha.desc())
        .all()
    )


@router.get("/mi-presupuesto/{reclamo_id}", response_model=PresupuestoOut | None)
def obtener_mi_presupuesto(reclamo_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """La última oferta del contratista logueado para el reclamo, que es la que puede
    editar o ajustar."""
    ficha = _ficha_del_usuario(db, usuario)
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    ofertas = estados_presupuesto.ofertas_del_contratista(reclamo, ficha.id)
    return ofertas[-1] if ofertas else None


@router.post("", response_model=ContratistaOut, status_code=201)
def crear_contratista(contratista: ContratistaCreate, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    nuevo_contratista = Contratista(**contratista.model_dump())
    db.add(nuevo_contratista)
    db.commit()
    db.refresh(nuevo_contratista)
    return nuevo_contratista


@router.get("", response_model=list[ContratistaOut])
def listar_contratistas(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    return db.query(Contratista).order_by(Contratista.nombre_empresa).all()


@router.get("/{contratista_id}", response_model=ContratistaOut)
def obtener_contratista(contratista_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    contratista = db.get(Contratista, contratista_id)
    if contratista is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")
    return contratista


@router.put("/{contratista_id}", response_model=ContratistaOut)
def actualizar_contratista(
    contratista_id: int, datos: ContratistaCreate, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)
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
def eliminar_contratista(contratista_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    contratista = db.get(Contratista, contratista_id)
    if contratista is None:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")
    db.delete(contratista)
    db.commit()
