"""Endpoints del Motor de IA."""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from core.ai import config as ai_config
from core.database import get_db
from core.dependencies import get_current_user
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.recomendacion_ia import RecomendacionIA, TipoRecomendacionIA
from models.usuario import Usuario
from schemas.ai import (
    AnalisisMediaOut,
    AuditoriaOut,
    ClasificacionOut,
    ContratistaSugeridoOut,
    DuplicadoOut,
    DuplicadosOut,
    EstimacionPreliminarOut,
    ExtraccionPresupuestoOut,
    InflacionSyncOut,
    ItemExtraidoOut,
    PipelineOut,
    RecomendacionIAOut,
    ReferenciasSyncOut,
    SeguimientoOut,
)
from services.ai import (
    auditoria,
    clasificacion,
    contratistas_sugeridos,
    duplicados,
    estimacion,
    grafo,
    inflacion,
    ocr_presupuesto,
    registro,
    sync_historicos,
    vision_reclamo,
)

router = APIRouter(prefix="/ai", tags=["ai"])


def _auditoria_out(informe) -> AuditoriaOut:
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
        aplicada = True

    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.CLASIFICACION,
        payload={
            "categoria": resultado.categoria,
            "prioridad": resultado.prioridad.value,
            "justificacion": resultado.justificacion,
            "aplicada": aplicar,
        },
        reclamo_id=reclamo.id,
        proveedor=resultado.proveedor,
        confianza=resultado.confianza,
    )
    db.commit()
    if aplicada:
        db.refresh(reclamo)

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
    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.DUPLICADOS,
        payload={
            "semantico": ai_config.duplicados_semanticos_enabled(),
            "candidatos": [
                {
                    "reclamo_id": c.reclamo_id,
                    "similitud": c.similitud,
                    "categoria": c.categoria,
                }
                for c in candidatos
            ],
        },
        reclamo_id=reclamo.id,
        proveedor=(
            ai_config.ai_provider_name()
            if ai_config.duplicados_semanticos_enabled()
            else "jaccard"
        ),
    )
    db.commit()

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
    auditoria.persistir_informe(db, informe)
    db.commit()
    return _auditoria_out(informe)


@router.get("/presupuestos/{presupuesto_id}/auditoria", response_model=AuditoriaOut)
def obtener_ultima_auditoria(
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if presupuesto is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    evento = (
        db.query(RecomendacionIA)
        .filter(
            RecomendacionIA.presupuesto_id == presupuesto_id,
            RecomendacionIA.tipo == TipoRecomendacionIA.AUDITORIA,
        )
        .order_by(RecomendacionIA.id.desc())
        .first()
    )
    if evento is None:
        raise HTTPException(status_code=404, detail="Todavía no hay auditoría para este presupuesto")

    try:
        payload = json.loads(evento.payload)
    except json.JSONDecodeError:
        payload = {}

    total_p = payload.get("total_presupuesto")
    total_e = payload.get("total_estimacion")
    desvio_abs = payload.get("desvio_absoluto")
    if desvio_abs is None and total_p is not None and total_e is not None:
        desvio_abs = float(total_p) - float(total_e)

    return AuditoriaOut(
        presupuesto_id=presupuesto_id,
        reclamo_id=evento.reclamo_id or presupuesto.reclamo_id,
        total_presupuesto=Decimal(str(total_p if total_p is not None else 0)),
        total_estimacion=Decimal(str(total_e)) if total_e is not None else None,
        desvio_absoluto=Decimal(str(desvio_abs)) if desvio_abs is not None else None,
        desvio_porcentual=Decimal(str(payload["desvio_porcentual"]))
        if payload.get("desvio_porcentual") is not None
        else None,
        recomendacion=payload.get("recomendacion") or "REVISAR",
        notas_tecnicas=payload.get("notas_tecnicas") or "",
        proveedor_notas=evento.proveedor or "n/a",
        sin_estimacion=bool(payload.get("sin_estimacion")),
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


@router.post("/referencias/sync", response_model=ReferenciasSyncOut)
def sincronizar_referencias(
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    resultado = sync_historicos.sync_desde_presupuestos(db)
    db.commit()
    return ReferenciasSyncOut(
        creadas=resultado.creadas,
        actualizadas=resultado.actualizadas,
        mensaje=(
            "Referencias actualizadas desde presupuestos "
            f"(+{resultado.creadas} / ~{resultado.actualizadas})."
        ),
    )


@router.get("/recomendaciones", response_model=list[RecomendacionIAOut])
def listar_recomendaciones(
    reclamo_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    q = db.query(RecomendacionIA).order_by(RecomendacionIA.fecha.desc())
    if reclamo_id is not None:
        q = q.filter(RecomendacionIA.reclamo_id == reclamo_id)
    return q.limit(100).all()


@router.post("/reclamos/{reclamo_id}/orquestar", response_model=PipelineOut)
def orquestar_reclamo(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    try:
        estado = grafo.ejecutar_pipeline(db, reclamo)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Falló el pipeline IA: {exc}") from exc

    dups = estado.get("duplicados") or []
    return PipelineOut(
        reclamo_id=reclamo_id,
        pasos=estado.get("pasos") or [],
        categoria=estado.get("categoria"),
        prioridad=estado.get("prioridad"),
        confianza=estado.get("confianza"),
        justificacion=estado.get("justificacion"),
        razonamiento=estado.get("razonamiento"),
        duplicados=dups,
        estimacion_id=estado.get("estimacion_id"),
        total=estado.get("total"),
        requiere_revision=bool(estado.get("requiere_revision")),
        error=estado.get("error"),
    )


@router.post("/seguimiento/ejecutar", response_model=SeguimientoOut)
def ejecutar_seguimiento_contratistas(
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    from services.seguimiento import ejecutar_seguimiento, seguimiento_horas

    resultado = ejecutar_seguimiento(db)
    db.commit()
    return SeguimientoOut(
        enviados=resultado.enviados,
        omitidos=resultado.omitidos,
        umbral_horas=seguimiento_horas(),
        mensaje=(
            f"Recordatorios enviados: {resultado.enviados}. "
            f"Omitidos: {resultado.omitidos}."
        ),
    )


@router.get(
    "/reclamos/{reclamo_id}/contratistas-sugeridos",
    response_model=list[ContratistaSugeridoOut],
)
def listar_contratistas_sugeridos(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    sugeridos = contratistas_sugeridos.sugerir_para_reclamo(db, reclamo)
    return [
        ContratistaSugeridoOut(
            contratista_id=s.contratista_id,
            nombre_empresa=s.nombre_empresa,
            especialidad=s.especialidad,
            calificacion=s.calificacion,
            carga_activa=s.carga_activa,
            score=s.score,
            motivos=s.motivos,
        )
        for s in sugeridos
    ]


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
        enriquecido = True

    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.VISION,
        payload={
            "hallazgos": resultado.hallazgos,
            "severidad": resultado.severidad,
            "sugerencia_descripcion": resultado.sugerencia_descripcion,
            "fotos_analizadas": resultado.fotos_analizadas,
            "enriquecido": enriquecido,
        },
        reclamo_id=reclamo.id,
        proveedor=resultado.proveedor,
    )
    db.commit()

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
        registro.registrar(
            db,
            tipo=TipoRecomendacionIA.OCR,
            payload={
                "adjunto_id": resultado.adjunto_id,
                "url": resultado.url,
                "tipo": resultado.tipo.value,
                "metodo": resultado.metodo,
                "items": [
                    {
                        "descripcion": i.descripcion,
                        "cantidad": float(i.cantidad),
                        "costo_unitario": float(i.costo_unitario),
                    }
                    for i in resultado.items
                ],
            },
            proveedor=resultado.proveedor,
        )
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
