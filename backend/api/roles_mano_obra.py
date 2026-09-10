from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin, get_current_user
from models.presupuesto import ItemPresupuesto, TipoItemPresupuesto
from models.rol_mano_obra import RolManoObra
from models.usuario import Usuario
from schemas.rol_mano_obra import RolManoObraCreate, RolManoObraOut

router = APIRouter(prefix="/roles-mano-obra", tags=["roles-mano-obra"])


@router.get("", response_model=list[RolManoObraOut])
def listar_roles(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    return db.query(RolManoObra).order_by(RolManoObra.nombre).all()


@router.post("", response_model=RolManoObraOut, status_code=201)
def crear_rol(
    datos: RolManoObraCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    nombre = datos.nombre.strip()
    if db.query(RolManoObra).filter(RolManoObra.nombre.ilike(nombre)).first():
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre")
    rol = RolManoObra(nombre=nombre)
    db.add(rol)
    db.commit()
    db.refresh(rol)
    return rol


@router.put("/{rol_id}", response_model=RolManoObraOut)
def actualizar_rol(
    rol_id: int,
    datos: RolManoObraCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    rol = db.get(RolManoObra, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    nombre = datos.nombre.strip()
    duplicado = (
        db.query(RolManoObra)
        .filter(RolManoObra.nombre.ilike(nombre), RolManoObra.id != rol_id)
        .first()
    )
    if duplicado:
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre")
    rol.nombre = nombre
    db.commit()
    db.refresh(rol)
    return rol


@router.delete("/{rol_id}", status_code=204)
def eliminar_rol(
    rol_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    rol = db.get(RolManoObra, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    en_uso = (
        db.query(ItemPresupuesto)
        .filter(
            ItemPresupuesto.tipo == TipoItemPresupuesto.MANO_OBRA,
            ItemPresupuesto.descripcion == rol.nombre,
        )
        .first()
    )
    if en_uso:
        raise HTTPException(
            status_code=409,
            detail="No se puede borrar: hay presupuestos que usan este rol",
        )
    db.delete(rol)
    db.commit()
