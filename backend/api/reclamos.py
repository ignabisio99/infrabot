import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.dependencies import get_current_admin, get_current_user
from core.storage import storage
from core.whatsapp_client import enviar_mensaje
from core.whatsapp_handler import iniciar_espera_info
from models.contratista import Contratista
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.lista_contratistas import ListaContratistas
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import Usuario
from models.historial_estado_reclamo import HistorialEstadoReclamo
from schemas.lista_contratistas import (
    NotificacionResultado,
    NotificarContratistasIn,
    NotificarContratistasOut,
    SolicitarInformacionIn,
    SolicitudPresupuestoOut,
)
from schemas.reclamo import (
    CambioEstadoReclamo,
    FotoReclamoOut,
    HistorialEstadoReclamoOut,
    ReclamoCreate,
    ReclamoOut,
)
from services import estados_reclamo
from services.ai.automatico import post_alta_reclamo, post_fotos_reclamo

logger = logging.getLogger(__name__)
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

router = APIRouter(prefix="/reclamos", tags=["reclamos"])

TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TIPOS_VIDEO_PERMITIDOS = {"video/mp4", "video/quicktime", "video/webm", "video/3gpp"}
TIPOS_MEDIA_PERMITIDOS = TIPOS_IMAGEN_PERMITIDOS | TIPOS_VIDEO_PERMITIDOS


def _con_fotos(query):
    return query.options(joinedload(Reclamo.fotos))


@router.post("", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    nuevo_reclamo = Reclamo(**reclamo.model_dump(), estado=estados_reclamo.ESTADO_INICIAL)
    db.add(nuevo_reclamo)
    estados_reclamo.registrar_estado_inicial(db, nuevo_reclamo)
    db.commit()
    db.refresh(nuevo_reclamo)
    post_alta_reclamo(db, nuevo_reclamo)
    try:
        db.commit()
        db.refresh(nuevo_reclamo)
    except Exception:
        logger.exception("No se pudo persistir la IA automática del reclamo %s", nuevo_reclamo.id)
        db.rollback()
    return nuevo_reclamo


@router.get("", response_model=list[ReclamoOut])
def listar_reclamos(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    return _con_fotos(db.query(Reclamo)).order_by(Reclamo.fecha_creacion.desc()).all()


@router.get("/{reclamo_id}", response_model=ReclamoOut)
def obtener_reclamo(reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return reclamo


@router.put("/{reclamo_id}", response_model=ReclamoOut)
def actualizar_reclamo(reclamo_id: int, datos: ReclamoCreate, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    # `estado` no está en ReclamoCreate a propósito: sólo se mueve por
    # POST /reclamos/{id}/estado, que valida la transición y deja historial.
    for campo, valor in datos.model_dump().items():
        setattr(reclamo, campo, valor)
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.post("/{reclamo_id}/estado", response_model=ReclamoOut)
def cambiar_estado_reclamo(
    reclamo_id: int,
    datos: CambioEstadoReclamo,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    try:
        # TODO: validar contra el rol del usuario cuando existan (gestor/contratista).
        estados_reclamo.cambiar_estado(
            db, reclamo, datos.estado, motivo=datos.motivo, usuario_id=user.id
        )
    except estados_reclamo.TransicionInvalida as error:
        raise HTTPException(status_code=409, detail=str(error))
    except estados_reclamo.MotivoRequerido as error:
        raise HTTPException(status_code=422, detail=str(error))

    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.get("/{reclamo_id}/historial", response_model=list[HistorialEstadoReclamoOut])
def listar_historial_reclamo(
    reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)
):
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return (
        db.query(HistorialEstadoReclamo)
        .filter(HistorialEstadoReclamo.reclamo_id == reclamo_id)
        .order_by(HistorialEstadoReclamo.fecha, HistorialEstadoReclamo.id)
        .all()
    )


@router.delete("/{reclamo_id}", status_code=204)
def eliminar_reclamo(reclamo_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    tiene_presupuestos = (
        db.query(Presupuesto).filter(Presupuesto.reclamo_id == reclamo_id).first() is not None
    )
    if tiene_presupuestos:
        raise HTTPException(
            status_code=409, detail="No se puede eliminar el reclamo: tiene presupuestos asociados"
        )
    for foto in reclamo.fotos:
        storage.eliminar(foto.url)
    db.delete(reclamo)
    db.commit()


@router.post("/{reclamo_id}/fotos", response_model=FotoReclamoOut, status_code=201)
def subir_foto(reclamo_id: int, archivo: UploadFile = File(...), db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    if archivo.content_type not in TIPOS_MEDIA_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser una imagen (jpg, png, webp) o video (mp4, mov, webm, 3gpp)",
        )

    tipo = TipoMedia.VIDEO if archivo.content_type in TIPOS_VIDEO_PERMITIDOS else TipoMedia.IMAGEN
    url = storage.guardar(archivo, f"reclamos/{reclamo_id}")

    nueva_foto = FotoReclamo(
        reclamo_id=reclamo_id, nombre_archivo=archivo.filename, url=url, tipo=tipo
    )
    db.add(nueva_foto)
    db.commit()
    db.refresh(nueva_foto)
    if tipo == TipoMedia.IMAGEN:
        recargado = (
            _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
        )
        if recargado is not None:
            post_fotos_reclamo(db, recargado)
            try:
                db.commit()
            except Exception:
                logger.exception("No se pudo persistir el análisis de fotos del reclamo %s", reclamo_id)
                db.rollback()
    return nueva_foto


@router.delete("/{reclamo_id}/fotos/{foto_id}", status_code=204)
def eliminar_foto(reclamo_id: int, foto_id: int, db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    foto = (
        db.query(FotoReclamo)
        .filter(FotoReclamo.id == foto_id, FotoReclamo.reclamo_id == reclamo_id)
        .first()
    )
    if foto is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    storage.eliminar(foto.url)
    db.delete(foto)
    db.commit()


@router.post("/{reclamo_id}/notificar-contratistas", response_model=NotificarContratistasOut)
def notificar_contratistas(
    reclamo_id: int,
    datos: NotificarContratistasIn,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Notifica por WhatsApp a contratistas para que carguen presupuesto.

    Se debe enviar `contratista_ids` (selección manual) o `lista_id` (lista predefinida).
    Solo para administradores.
    """
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    # Solo se puede convocar contratistas cuando el reclamo está pendiente de presupuesto.
    if reclamo.estado != EstadoReclamo.PENDIENTE_PRESUPUESTO:
        raise HTTPException(
            status_code=409,
            detail="Solo se puede notificar contratistas cuando el reclamo está pendiente de presupuesto",
        )

    # Resolver la lista de contratistas destino
    if datos.lista_id is not None:
        lista = db.get(ListaContratistas, datos.lista_id)
        if lista is None:
            raise HTTPException(status_code=404, detail="Lista no encontrada")
        contratistas = list(lista.contratistas)
    elif datos.contratista_ids:
        contratistas = db.query(Contratista).filter(Contratista.id.in_(datos.contratista_ids)).all()
        encontrados = {c.id for c in contratistas}
        faltantes = set(datos.contratista_ids) - encontrados
        if faltantes:
            raise HTTPException(
                status_code=404, detail=f"Contratistas no encontrados: {sorted(faltantes)}"
            )
    else:
        raise HTTPException(
            status_code=422,
            detail="Debés indicar 'contratista_ids' o 'lista_id'",
        )

    if not contratistas:
        raise HTTPException(status_code=422, detail="No hay contratistas para notificar")

    link = f"{APP_URL}/portal/reclamos/{reclamo_id}/presupuestar"
    mensaje = (
        f"🔔 Fue seleccionado para cargar el presupuesto del reclamo #{reclamo_id}.\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n\n"
        f"Entre al siguiente link para ver más en detalle y cargar su presupuesto:\n{link}"
    )

    resultados: list[NotificacionResultado] = []
    enviados = 0
    for c in contratistas:
        error = None
        ok = False
        try:
            respuesta = enviar_mensaje(c.telefono, mensaje)
            # La API de Meta devuelve un dict con "messages" si el envío fue aceptado
            ok = "messages" in respuesta
            if not ok:
                error = str(respuesta.get("error", respuesta))
        except Exception as e:  # noqa: BLE001 - queremos reportar por contratista sin cortar
            error = str(e)

        if ok:
            enviados += 1
            # Registrar la solicitud (idempotente: no duplicar si ya existía)
            ya_existe = (
                db.query(SolicitudPresupuesto)
                .filter(
                    SolicitudPresupuesto.reclamo_id == reclamo_id,
                    SolicitudPresupuesto.contratista_id == c.id,
                )
                .first()
            )
            if not ya_existe:
                db.add(SolicitudPresupuesto(reclamo_id=reclamo_id, contratista_id=c.id))

        resultados.append(
            NotificacionResultado(
                contratista_id=c.id,
                nombre_empresa=c.nombre_empresa,
                telefono=c.telefono,
                enviado=ok,
                error=error,
            )
        )

    # Persistir las solicitudes registradas (el reclamo ya está en PENDIENTE_PRESUPUESTO).
    if enviados > 0:
        db.commit()

    return NotificarContratistasOut(
        total=len(contratistas),
        enviados=enviados,
        resultados=resultados,
    )


@router.get("/{reclamo_id}/solicitudes-presupuesto", response_model=list[SolicitudPresupuestoOut])
def listar_solicitudes_presupuesto(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Lista los contratistas a los que se les solicitó presupuesto para el reclamo,
    indicando si ya lo cargaron y el id del presupuesto en ese caso. Solo admins.
    """
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    solicitudes = (
        db.query(SolicitudPresupuesto)
        .filter(SolicitudPresupuesto.reclamo_id == reclamo_id)
        .order_by(SolicitudPresupuesto.fecha_solicitud)
        .all()
    )

    # Presupuestos ya cargados para este reclamo, indexados por contratista
    presupuestos = (
        db.query(Presupuesto).filter(Presupuesto.reclamo_id == reclamo_id).all()
    )
    presupuesto_por_contratista = {p.contratista_id: p.id for p in presupuestos}

    resultado = []
    for s in solicitudes:
        c = s.contratista
        presupuesto_id = presupuesto_por_contratista.get(s.contratista_id)
        resultado.append(
            SolicitudPresupuestoOut(
                contratista_id=s.contratista_id,
                nombre_empresa=c.nombre_empresa if c else "—",
                especialidad=c.especialidad if c else "—",
                telefono=c.telefono if c else "—",
                fecha_solicitud=s.fecha_solicitud,
                presupuesto_cargado=presupuesto_id is not None,
                presupuesto_id=presupuesto_id,
            )
        )
    return resultado


@router.post("/{reclamo_id}/solicitar-informacion", response_model=NotificacionResultado)
def solicitar_informacion(
    reclamo_id: int,
    datos: SolicitarInformacionIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Un contratista pide información adicional sobre el reclamo.

    El bot reenvía el mensaje por WhatsApp a quien creó el reclamo (telefono_creador).
    """
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    if not reclamo.telefono_creador:
        raise HTTPException(
            status_code=409,
            detail="Este reclamo no fue creado por WhatsApp, no hay un contacto al que reenviar el pedido.",
        )

    # Nombre del contratista que solicita (si tiene ficha vinculada)
    ficha = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    nombre_contratista = ficha.nombre_empresa if ficha else usuario.nombre

    mensaje = (
        f"ℹ️ *Solicitud de información — Reclamo #{reclamo_id}*\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n\n"
        f"El contratista *{nombre_contratista}* necesita más información para poder "
        f"cargar el presupuesto:\n\n"
        f"\"{datos.mensaje.strip()}\"\n\n"
        f"Respondé a este mensaje con el texto y/o las fotos o videos que quieras sumar. "
        f"Cuando termines, escribí *listo*."
    )

    error = None
    ok = False
    try:
        respuesta = enviar_mensaje(reclamo.telefono_creador, mensaje)
        ok = "messages" in respuesta
        if not ok:
            error = str(respuesta.get("error", respuesta))
    except Exception as e:  # noqa: BLE001
        error = str(e)

    if not ok:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo enviar el mensaje al creador del reclamo. {error or ''}".strip(),
        )

    # Dejar al creador esperando que responda con la información adicional.
    # Guardamos el contacto del contratista para avisarle cuando el creador termine.
    iniciar_espera_info(
        reclamo.telefono_creador,
        reclamo_id,
        telefono_contratista=ficha.telefono if ficha else "",
        nombre_contratista=nombre_contratista,
    )

    return NotificacionResultado(
        contratista_id=ficha.id if ficha else 0,
        nombre_empresa=nombre_contratista,
        telefono=reclamo.telefono_creador,
        enviado=True,
        error=None,
    )


@router.get("/{reclamo_id}/visita")
def obtener_visita_reclamo(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    """Devuelve la coordinación de visita del reclamo (o null si no hay).

    No usa response_model para poder devolver null sin error cuando aún no hay visita.
    """
    from models.visita import Visita
    from schemas.visita import VisitaOut

    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    visita = (
        db.query(Visita)
        .filter(Visita.reclamo_id == reclamo_id)
        .order_by(Visita.id.desc())
        .first()
    )
    if visita is None:
        return None
    return VisitaOut.model_validate(visita)
