from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from models.contratista import Contratista
from models.reclamo import Reclamo
from models.usuario import TipoUsuario, Usuario
from models.visita import Visita
from schemas.visita import VisitaCalendarioOut

router = APIRouter(prefix="/visitas", tags=["visitas"])


@router.get("", response_model=list[VisitaCalendarioOut])
def listar_visitas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    consulta = (
        db.query(Visita, Reclamo, Contratista)
        .join(Reclamo, Reclamo.id == Visita.reclamo_id)
        .join(Contratista, Contratista.id == Visita.contratista_id)
    )

    if usuario.tipo not in {
        TipoUsuario.ADMINISTRADOR,
        TipoUsuario.INSPECTOR,
        TipoUsuario.CONTRATISTA,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permisos para consultar las visitas",
        )

    if usuario.tipo == TipoUsuario.CONTRATISTA:
        consulta = consulta.filter(Contratista.usuario_id == usuario.id)

    return [
        VisitaCalendarioOut(
            id=visita.id,
            reclamo_id=visita.reclamo_id,
            contratista_id=visita.contratista_id,
            estado=visita.estado,
            disponibilidades=visita.disponibilidades,
            horario_confirmado=visita.horario_confirmado,
            fecha_visita=visita.fecha_visita,
            nombre_escuela=reclamo.nombre_escuela,
            ubicacion=reclamo.ubicacion,
            nombre_empresa=contratista.nombre_empresa,
        )
        for visita, reclamo, contratista in consulta.order_by(Visita.fecha_visita, Visita.id).all()
    ]