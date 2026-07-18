from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.reclamo import Reclamo
from schemas.reclamo import ReclamoCreate, ReclamoOut

router = APIRouter(prefix="/reclamos", tags=["reclamos"])


@router.post("/crear", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db)):
    nuevo_reclamo = Reclamo(**reclamo.model_dump())
    db.add(nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
    return nuevo_reclamo
