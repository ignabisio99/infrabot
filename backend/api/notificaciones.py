from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.usuario import Usuario
from services import notificaciones as svc

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


class ConteoOut(BaseModel):
    no_leidas: int
    mensaje: str
    versiones_por_decidir: int
    # No suma a `no_leidas`: es trabajo de rutina, no un aviso. Lo muestra el menú lateral.
    reclamos_en_evaluacion: int


def _mensaje(n: int) -> str:
    if n <= 0:
        return "No hay reclamos en estado pendiente de intervención."
    if n == 1:
        return "Hay 1 reclamo en estado pendiente de intervención."
    return f"Hay {n} reclamos en estado pendiente de intervención."


@router.get("/conteo", response_model=ConteoOut)
def conteo(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    n = svc.contar_pendiente_intervencion(db)
    versiones = svc.contar_versiones_por_decidir(db)
    return ConteoOut(
        no_leidas=n + versiones,
        mensaje=_mensaje(n),
        versiones_por_decidir=versiones,
        reclamos_en_evaluacion=svc.contar_en_evaluacion(db),
    )
