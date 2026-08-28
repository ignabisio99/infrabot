"""CRUD de listas de contratistas. Solo para administradores.

Las listas son compartidas entre todos los administradores.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.contratista import Contratista
from models.lista_contratistas import ListaContratistas
from models.usuario import Usuario
from schemas.lista_contratistas import ListaContratistasCreate, ListaContratistasOut

router = APIRouter(prefix="/listas-contratistas", tags=["listas-contratistas"])


def _obtener_contratistas(db: Session, ids: list[int]) -> list[Contratista]:
    contratistas = db.query(Contratista).filter(Contratista.id.in_(ids)).all()
    encontrados = {c.id for c in contratistas}
    faltantes = set(ids) - encontrados
    if faltantes:
        raise HTTPException(
            status_code=404,
            detail=f"Contratistas no encontrados: {sorted(faltantes)}",
        )
    return contratistas


@router.post("", response_model=ListaContratistasOut, status_code=201)
def crear_lista(
    datos: ListaContratistasCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    contratistas = _obtener_contratistas(db, datos.contratista_ids)
    lista = ListaContratistas(nombre=datos.nombre, creada_por_id=admin.id)
    lista.contratistas = contratistas
    db.add(lista)
    db.commit()
    db.refresh(lista)
    return lista


@router.get("", response_model=list[ListaContratistasOut])
def listar_listas(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    return db.query(ListaContratistas).order_by(ListaContratistas.fecha_creacion.desc()).all()


@router.get("/{lista_id}", response_model=ListaContratistasOut)
def obtener_lista(lista_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    lista = db.get(ListaContratistas, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista


@router.put("/{lista_id}", response_model=ListaContratistasOut)
def actualizar_lista(
    lista_id: int,
    datos: ListaContratistasCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    lista = db.get(ListaContratistas, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    lista.nombre = datos.nombre
    lista.contratistas = _obtener_contratistas(db, datos.contratista_ids)
    db.commit()
    db.refresh(lista)
    return lista


@router.delete("/{lista_id}", status_code=204)
def eliminar_lista(lista_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    lista = db.get(ListaContratistas, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    db.delete(lista)
    db.commit()
