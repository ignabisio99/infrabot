from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.usuario import Usuario
from schemas.institucion import InstitucionOut
from services.instituciones import buscar_instituciones

router = APIRouter(prefix="/instituciones", tags=["instituciones"])


@router.get("", response_model=list[InstitucionOut])
def buscar(
    q: str = Query(""),
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Busca en el padrón para elegir la escuela al cargar un reclamo desde la web."""
    return buscar_instituciones(db, q, limite=limite)
