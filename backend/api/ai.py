"""Endpoints del Motor de IA."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from core.ai import config as ai_config
from core.database import get_db
from core.dependencies import get_current_user
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.usuario import Usuario
from schemas.ai import (
    AnalisisMediaOut,
    AuditoriaOut,
    ClasificacionOut,
    DuplicadoOut,
    DuplicadosOut,
    EstimacionPreliminarOut,
    ExtraccionPresupuestoOut,
    InflacionSyncOut,
    ItemExtraidoOut,
)
from services.ai import (
    auditoria,
    clasificacion,
    duplicados,
    estimacion,
    inflacion,
    ocr_presupuesto,
    vision_reclamo,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/reclamos/{reclamo_id}/clasificar", response_model=ClasificacionOut)
def clasificar_reclamo(
    reclamo_id: int,
    aplicar: bool = Query(False, description="Si true, actualiza categoria/prioridad del reclamo"),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    resultado = clasificacion.clasificar_reclamo(reclamo)
    aplicada = False
    if aplicar:
        clasificacion.aplicar_clasificacion(reclamo, resultado)
        db.commit()
        db.refresh(reclamo)
        aplicada = True

    return ClasificacionOut(
        reclamo_id=reclamo.id,
        categoria=resultado.categoria,
        prioridad=resultado.prioridad,
        confianza=resultado.confianza,
        justificacion=resultado.justificacion,
        proveedor=resultado.proveedor,
        aplicada=aplicada,
    )


@router.get("/reclamos/{reclamo_id}/duplicados", response_model=DuplicadosOut)
def listar_duplicados(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    candidatos = duplicados.buscar_duplicados(db, reclamo)
    return DuplicadosOut(
        reclamo_id=reclamo.id,
        candidatos=[
            DuplicadoOut(
                reclamo_id=c.reclamo_id,
                nombre_escuela=c.nombre_escuela,
                categoria=c.categoria,
                estado=c.estado,
                descripcion=c.descripcion,
                similitud=c.similitud,
            )
            for c in candidatos
        ],
    )


@router.post("/reclamos/{reclamo_id}/estimacion", response_model=EstimacionPreliminarOut, status_code=201)
def crear_estimacion(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    nueva = estimacion.generar_estimacion(db, reclamo, transicionar=True)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.get("/reclamos/{reclamo_id}/estimacion", response_model=EstimacionPreliminarOut)
def obtener_ultima_estimacion(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    ultima = estimacion.ultima_estimacion(db, reclamo_id)
    if ultima is None:
        raise HTTPException(status_code=404, detail="No hay estimación preliminar para este reclamo")
    return ultima


@router.post("/presupuestos/{presupuesto_id}/auditar", response_model=AuditoriaOut)
def auditar_presupuesto(
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    presupuesto = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.items))
        .filter(Presupuesto.id == presupuesto_id)
        .first()
    )
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    informe = auditoria.auditar_presupuesto(db, presupuesto)
    return AuditoriaOut(
        presupuesto_id=informe.presupuesto_id,
        reclamo_id=informe.reclamo_id,
        total_presupuesto=informe.total_presupuesto,
        total_estimacion=informe.total_estimacion,
        desvio_absoluto=informe.desvio_absoluto,
        desvio_porcentual=informe.desvio_porcentual,
        recomendacion=informe.recomendacion,
        notas_tecnicas=informe.notas_tecnicas,
        proveedor_notas=informe.proveedor_notas,
        sin_estimacion=informe.sin_estimacion,
    )


@router.post("/inflacion/sync", response_model=InflacionSyncOut)
def sincronizar_inflacion(
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    try:
        filas = inflacion.sync_indices(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo sincronizar IPC desde datos.gob.ar: {exc}",
        ) from exc
    return InflacionSyncOut(
        filas=filas,
        serie_id=ai_config.inflacion_serie_id(),
        mensaje=f"Cache IPC actualizado ({filas} períodos).",
    )


@router.post("/reclamos/{reclamo_id}/analizar-media", response_model=AnalisisMediaOut)
def analizar_media_reclamo(
    reclamo_id: int,
    enriquecer_descripcion: bool = Query(
        False,
        description="Si true, appende la sugerencia a observaciones (no pisa descripcion)",
    ),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.fotos))
        .filter(Reclamo.id == reclamo_id)
        .first()
    )
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    resultado = vision_reclamo.analizar_media_reclamo(db, reclamo)
    if resultado.fotos_analizadas == 0:
        raise HTTPException(
            status_code=422,
            detail="El reclamo no tiene fotos de tipo IMAGEN disponibles en disco",
        )

    enriquecido = False
    if enriquecer_descripcion and resultado.sugerencia_descripcion:
        nota = f"[IA visión] {resultado.sugerencia_descripcion}"
        if reclamo.observaciones:
            reclamo.observaciones = f"{reclamo.observaciones}\n{nota}"
        else:
            reclamo.observaciones = nota
        db.commit()
        enriquecido = True

    return AnalisisMediaOut(
        reclamo_id=resultado.reclamo_id,
        hallazgos=resultado.hallazgos,
        severidad=resultado.severidad,
        sugerencia_descripcion=resultado.sugerencia_descripcion,
        fotos_analizadas=resultado.fotos_analizadas,
        proveedor=resultado.proveedor,
        enriquecido=enriquecido,
    )


@router.post("/presupuestos/extraer", response_model=ExtraccionPresupuestoOut)
def extraer_presupuesto(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    try:
        resultado = ocr_presupuesto.extraer_items_desde_archivo(db, archivo)
        db.commit()
    except ocr_presupuesto.ExtraccionPresupuestoError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Error al extraer presupuesto: {exc}") from exc

    return ExtraccionPresupuestoOut(
        adjunto_id=resultado.adjunto_id,
        url=resultado.url,
        tipo=resultado.tipo,
        items=[
            ItemExtraidoOut(
                descripcion=i.descripcion,
                cantidad=i.cantidad,
                costo_unitario=i.costo_unitario,
            )
            for i in resultado.items
        ],
        proveedor=resultado.proveedor,
        metodo=resultado.metodo,
    )
