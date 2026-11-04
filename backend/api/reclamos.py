import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload, selectinload

from core.database import get_db
from core.dependencies import (
    get_current_admin,
    get_current_admin_o_inspector,
    get_current_contratista,
    get_current_inspector,
    get_current_user,
)
from core.storage import TIPOS_MEDIA, TIPOS_VIDEO, ArchivoInvalido, storage
from core.telefonos import mismo_telefono, normalizar_telefono_ar
from core.email import enviar_solicitud_presupuesto
from core.whatsapp_client import enviar_mensaje
from core.whatsapp_handler import iniciar_espera_info
from models.comentario_reclamo import ComentarioReclamo
from models.contratista import Contratista
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.lista_contratistas import ListaContratistas
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import HistorialEstadoReclamo
from schemas.lista_contratistas import (
    ContratistaYaNotificado,
    NotificacionResultado,
    NotificarContratistasIn,
    NotificarContratistasOut,
    SolicitarInformacionIn,
    SolicitudPresupuestoOut,
)
from schemas.presupuesto import AsignarOfertaExistenteIn, OfertaReutilizableOut
from schemas.reclamo import (
    CambioEstadoReclamo,
    ComentarioReclamoIn,
    ComentarioReclamoOut,
    FotoReclamoOut,
    HistorialEstadoReclamoOut,
    MovimientoPresupuestoOut,
    NotificarInspectoresIn,
    NotificarInspectoresOut,
    AvisoInspectorOut,
    ReclamoCreate,
    ReclamoOut,
    SolicitudInspeccionOut,
)
from services import (
    acceso_reclamos,
    avisos_presupuesto,
    coordinacion_visita,
    estados_presupuesto,
    estados_reclamo,
    solicitudes_inspeccion,
)
from services.ai.automatico import post_alta_reclamo, post_fotos_reclamo
from services.reabrir_convocatoria import (
    ReaperturaInvalida,
    asignar_oferta_existente,
    listar_ofertas_reutilizables,
    reabrir_por_inaccion,
)

logger = logging.getLogger(__name__)
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

router = APIRouter(prefix="/reclamos", tags=["reclamos"])



def _con_fotos(query):
    return query.options(
        joinedload(Reclamo.fotos).joinedload(FotoReclamo.usuario),
        # Para `ofertas_en_carrera` y `fecha_ultimo_movimiento`: sin esto, el listado hace
        # una consulta por reclamo.
        selectinload(Reclamo.presupuestos),
        selectinload(Reclamo.historial_estados),
    )


def _email_del_contratista(db: Session, contratista: Contratista) -> str | None:
    """Devuelve el email de la cuenta de usuario del contratista.

    Funciona igual para cuentas creadas por registro normal o por Google SSO (en ambos
    casos el email queda en el Usuario). Primero busca por el vínculo `usuario_id`; si
    la ficha todavía no está vinculada, cae a buscar por teléfono (últimos 8 dígitos).
    """
    import re

    if contratista.usuario_id:
        usuario = db.get(Usuario, contratista.usuario_id)
        if usuario and usuario.email:
            return usuario.email

    # Fallback: match por teléfono si la ficha no está vinculada aún.
    tel_ficha = re.sub(r"\D", "", contratista.telefono or "")
    if not tel_ficha:
        return None
    candidatos = db.query(Usuario).filter(Usuario.tipo == TipoUsuario.CONTRATISTA).all()
    for u in candidatos:
        tel_u = re.sub(r"\D", "", u.telefono or "")
        if tel_u and tel_u[-8:] == tel_ficha[-8:] and u.email:
            return u.email
    return None


@router.post("", response_model=ReclamoOut, status_code=201)
def crear_reclamo(reclamo: ReclamoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_admin)):
    datos = reclamo.model_dump()
    # Sin este número el contratista carga fechas y el bot las descarta: no tiene a
    # quién pedirle que elija un horario.
    if not datos.get("telefono_creador"):
        crudo = (usuario.telefono or "").strip()
        datos["telefono_creador"] = normalizar_telefono_ar(crudo) if crudo else None
    nuevo_reclamo = Reclamo(**datos, estado=estados_reclamo.ESTADO_INICIAL)
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
def listar_reclamos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    # Un contratista solo ve los reclamos a los que lo convocaron.
    query = acceso_reclamos.filtrar_visibles(db, _con_fotos(db.query(Reclamo)), usuario)
    return query.order_by(Reclamo.fecha_creacion.desc()).all()


@router.get("/{reclamo_id}", response_model=ReclamoOut)
def obtener_reclamo(reclamo_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    acceso_reclamos.exigir_acceso(db, reclamo_id, usuario)
    return reclamo


@router.put("/{reclamo_id}", response_model=ReclamoOut)
def actualizar_reclamo(reclamo_id: int, datos: ReclamoCreate, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    # `estado` no está en ReclamoCreate a propósito: sólo se mueve por
    # POST /reclamos/{id}/estado, que valida la transición y deja historial.
    # Un PUT que no manda el teléfono (el formulario viejo) no tiene que borrarlo.
    cambios = datos.model_dump(exclude_unset=True)
    # Si es el mismo número, queda como lo guardó el bot: normalizado a +54 se manda a
    # WhatsApp con otro formato y desordena las búsquedas por teléfono.
    if mismo_telefono(cambios.get("telefono_creador"), reclamo.telefono_creador):
        del cambios["telefono_creador"]
    for campo, valor in cambios.items():
        setattr(reclamo, campo, valor)
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.post("/{reclamo_id}/estado", response_model=ReclamoOut)
def cambiar_estado_reclamo(
    reclamo_id: int,
    datos: CambioEstadoReclamo,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_admin),
):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    # Las ofertas en carrera se quedan sin evaluación: sin el aviso, el contratista
    # seguiría esperando una decisión o corrigiendo algo que ya no sirve.
    vigentes = [p for p in reclamo.presupuestos if estados_presupuesto.esta_vigente(p)]
    # Se busca antes del cambio: cancelar el reclamo cancela también la visita.
    visita = coordinacion_visita.visita_vigente(db, reclamo)

    try:
        estados_reclamo.cambiar_estado(
            db, reclamo, datos.estado, motivo=datos.motivo, usuario_id=user.id
        )
    except estados_reclamo.TransicionInvalida as error:
        raise HTTPException(status_code=409, detail=str(error))
    except estados_reclamo.MotivoRequerido as error:
        raise HTTPException(status_code=422, detail=str(error))

    db.commit()
    db.refresh(reclamo)
    if reclamo.estado is EstadoReclamo.CANCELADO:
        for presupuesto in vigentes:
            avisos_presupuesto.avisar_reclamo_cancelado(db, presupuesto, datos.motivo)
        if visita is not None:
            coordinacion_visita.avisar_visita_cancelada(db, visita, datos.motivo)
    return reclamo


@router.post("/{reclamo_id}/reabrir-convocatoria", response_model=ReclamoOut)
def reabrir_convocatoria(
    reclamo_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_admin),
):
    """Cancela el presupuesto aprobado y vuelve a PENDIENTE_PRESUPUESTO para convocar a otro."""
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    try:
        reabrir_por_inaccion(db, reclamo, usuario_id=user.id)
    except ReaperturaInvalida as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (
        estados_reclamo.TransicionInvalida,
        estados_presupuesto.TransicionInvalida,
        estados_presupuesto.MotivoRequerido,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.get("/{reclamo_id}/ofertas-reutilizables", response_model=list[OfertaReutilizableOut])
def ofertas_reutilizables(
    reclamo_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return listar_ofertas_reutilizables(db, reclamo)


@router.post("/{reclamo_id}/asignar-oferta-existente", response_model=ReclamoOut)
def asignar_oferta_ya_enviada(
    reclamo_id: int,
    datos: AsignarOfertaExistenteIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_admin),
):
    reclamo = _con_fotos(db.query(Reclamo)).filter(Reclamo.id == reclamo_id).first()
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    try:
        asignar_oferta_existente(db, reclamo, datos.presupuesto_id, usuario_id=user.id)
    except ReaperturaInvalida as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (
        estados_reclamo.TransicionInvalida,
        estados_presupuesto.TransicionInvalida,
        estados_presupuesto.MotivoRequerido,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    db.commit()
    db.refresh(reclamo)
    return reclamo


@router.get("/{reclamo_id}/historial", response_model=list[HistorialEstadoReclamoOut])
def listar_historial_reclamo(
    reclamo_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)
):
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    acceso_reclamos.exigir_acceso(db, reclamo_id, usuario)
    return (
        db.query(HistorialEstadoReclamo)
        .filter(HistorialEstadoReclamo.reclamo_id == reclamo_id)
        .order_by(HistorialEstadoReclamo.fecha, HistorialEstadoReclamo.id)
        .all()
    )


@router.get(
    "/{reclamo_id}/movimientos-presupuestos", response_model=list[MovimientoPresupuestoOut]
)
def listar_movimientos_presupuestos(
    reclamo_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)
):
    """Todos los cambios de estado de los presupuestos del reclamo, en orden, para la
    línea de tiempo. Pedir ajustes o rechazar una oferta no siempre cambia el estado del
    reclamo, así que no queda en su historial. Solo admins, igual que la pestaña de
    presupuestos."""
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    filas = (
        db.query(HistorialEstadoPresupuesto, Presupuesto)
        .join(Presupuesto, Presupuesto.id == HistorialEstadoPresupuesto.presupuesto_id)
        .options(joinedload(Presupuesto.contratista))
        .filter(Presupuesto.reclamo_id == reclamo_id)
        .order_by(HistorialEstadoPresupuesto.fecha, HistorialEstadoPresupuesto.id)
        .all()
    )
    return [
        MovimientoPresupuestoOut(
            presupuesto_id=presupuesto.id,
            nombre_empresa=presupuesto.contratista.nombre_empresa if presupuesto.contratista else "—",
            estado_anterior=historial.estado_anterior,
            estado_nuevo=historial.estado_nuevo,
            motivo=historial.motivo,
            fecha=historial.fecha,
        )
        for historial, presupuesto in filas
    ]


@router.get("/{reclamo_id}/comentarios", response_model=list[ComentarioReclamoOut])
def listar_comentarios_reclamo(
    reclamo_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)
):
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    acceso_reclamos.exigir_acceso(db, reclamo_id, usuario)
    return (
        db.query(ComentarioReclamo)
        .options(joinedload(ComentarioReclamo.usuario))
        .filter(ComentarioReclamo.reclamo_id == reclamo_id)
        .order_by(ComentarioReclamo.fecha, ComentarioReclamo.id)
        .all()
    )


@router.post("/{reclamo_id}/comentarios", response_model=ComentarioReclamoOut, status_code=201)
def crear_comentario_reclamo(
    reclamo_id: int,
    datos: ComentarioReclamoIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_inspector),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    if reclamo.estado in estados_reclamo.ESTADOS_FINALES:
        raise HTTPException(
            status_code=409,
            detail=f'No se puede comentar un reclamo en estado "{reclamo.estado.etiqueta}"',
        )

    comentario = ComentarioReclamo(
        reclamo_id=reclamo_id, usuario_id=usuario.id, texto=datos.texto
    )
    db.add(comentario)
    solicitudes_inspeccion.marcar_atendidas(db, reclamo_id, usuario)
    db.commit()
    db.refresh(comentario)
    return comentario


@router.delete("/{reclamo_id}", status_code=204)
def eliminar_reclamo(reclamo_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
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
def subir_foto(
    reclamo_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_admin_o_inspector),
):
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    # Igual que con los comentarios: lo que aporta el inspector queda en el expediente
    # mientras el reclamo está abierto. El admin puede seguir cargando fotos siempre.
    if usuario.es_inspector and reclamo.estado in estados_reclamo.ESTADOS_FINALES:
        raise HTTPException(
            status_code=409,
            detail=f'No se pueden agregar fotos a un reclamo en estado "{reclamo.estado.etiqueta}"',
        )

    # Tipo, tamaño y contenido los valida el storage; la extensión con la que se guarda
    # sale del tipo, no del nombre que manda el cliente.
    try:
        url = storage.guardar(archivo, f"reclamos/{reclamo_id}", TIPOS_MEDIA)
    except ArchivoInvalido as e:
        detalle = e.mensaje
        if e.status_code == 400 and "permitido" in detalle:
            detalle = "El archivo debe ser una imagen (jpg, png, webp) o video (mp4, mov, webm, 3gpp)"
        raise HTTPException(status_code=e.status_code, detail=detalle) from e
    tipo = TipoMedia.VIDEO if archivo.content_type in TIPOS_VIDEO else TipoMedia.IMAGEN

    nueva_foto = FotoReclamo(
        reclamo_id=reclamo_id,
        # Solo se muestra (texto); se guarda con un nombre generado.
        nombre_archivo=(archivo.filename or "archivo")[:255],
        url=url,
        tipo=tipo,
        usuario_id=usuario.id,
    )
    db.add(nueva_foto)
    solicitudes_inspeccion.marcar_atendidas(db, reclamo_id, usuario)
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
def eliminar_foto(
    reclamo_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_admin_o_inspector),
):
    foto = (
        db.query(FotoReclamo)
        .filter(FotoReclamo.id == foto_id, FotoReclamo.reclamo_id == reclamo_id)
        .first()
    )
    if foto is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    if usuario.es_inspector:
        if foto.usuario_id != usuario.id:
            raise HTTPException(status_code=403, detail="Solo podés quitar las fotos que subiste")
        if foto.reclamo.estado in estados_reclamo.ESTADOS_FINALES:
            raise HTTPException(
                status_code=409,
                detail=f'No se pueden quitar fotos de un reclamo en estado "{foto.reclamo.estado.etiqueta}"',
            )
        # Los contratistas presupuestan mirando las fotos: si el inspector quita una, queda
        # constancia en los comentarios del reclamo.
        db.add(
            ComentarioReclamo(
                reclamo_id=reclamo_id,
                usuario_id=None,
                texto=f"[Sistema]\n{usuario.nombre} (inspector) quitó la foto {foto.nombre_archivo}.",
            )
        )

    url = foto.url
    db.delete(foto)
    db.commit()
    storage.eliminar(url)


def _solicitud_out(solicitud) -> SolicitudInspeccionOut:
    return SolicitudInspeccionOut(
        id=solicitud.id,
        reclamo_id=solicitud.reclamo_id,
        nombre_escuela=solicitud.reclamo.nombre_escuela,
        estado_reclamo=solicitud.reclamo.estado,
        inspector_id=solicitud.inspector_id,
        inspector_nombre=solicitud.inspector.nombre,
        solicitado_por_nombre=solicitud.solicitado_por.nombre if solicitud.solicitado_por else None,
        mensaje=solicitud.mensaje,
        fecha=solicitud.fecha,
        atendida_en=solicitud.atendida_en,
    )


@router.get("/inspeccion/pendientes", response_model=list[SolicitudInspeccionOut])
def listar_mis_pedidos_de_inspeccion(
    db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_inspector)
):
    """Reclamos en los que le pidieron información al inspector y todavía no aportó nada."""
    return [_solicitud_out(s) for s in solicitudes_inspeccion.pendientes_de(db, usuario)]


@router.get("/{reclamo_id}/solicitudes-inspeccion", response_model=list[SolicitudInspeccionOut])
def listar_solicitudes_inspeccion(
    reclamo_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_admin_o_inspector),
):
    """Pedidos de información del reclamo: todos para el admin, los propios para el inspector."""
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return [
        _solicitud_out(s) for s in solicitudes_inspeccion.del_reclamo(db, reclamo_id, usuario)
    ]


@router.post("/{reclamo_id}/notificar-inspectores", response_model=NotificarInspectoresOut)
def notificar_inspectores(
    reclamo_id: int,
    datos: NotificarInspectoresIn,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    """Pide a inspectores información adicional del reclamo: les llega por WhatsApp y
    email, y les aparece en la app hasta que comenten o suban una foto. Solo admins."""
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    if reclamo.estado in estados_reclamo.ESTADOS_FINALES:
        raise HTTPException(
            status_code=409,
            detail=f'No se puede pedir información de un reclamo en estado "{reclamo.estado.etiqueta}"',
        )

    ids = set(datos.inspector_ids)
    inspectores = (
        db.query(Usuario)
        .filter(
            Usuario.id.in_(ids),
            Usuario.tipo == TipoUsuario.INSPECTOR,
            Usuario.estado == EstadoUsuario.APROBADO,
        )
        .all()
    )
    if len(inspectores) != len(ids):
        raise HTTPException(status_code=404, detail="Alguno de los inspectores elegidos no existe")

    resultados = solicitudes_inspeccion.notificar(db, reclamo, inspectores, datos.mensaje, admin)
    db.commit()
    return NotificarInspectoresOut(
        total=len(resultados),
        resultados=[
            AvisoInspectorOut(
                inspector_id=r.inspector.id,
                nombre=r.inspector.nombre,
                whatsapp=r.whatsapp,
                email=r.email,
            )
            for r in resultados
        ],
    )


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
        # Siguen en la lista por si se los reactiva, pero no se los convoca.
        contratistas = [c for c in lista.contratistas if not c.dado_de_baja]
        if lista.contratistas and not contratistas:
            raise HTTPException(
                status_code=422,
                detail="Todos los contratistas de la lista están dados de baja",
            )
    elif datos.contratista_ids:
        contratistas = db.query(Contratista).filter(Contratista.id.in_(datos.contratista_ids)).all()
        encontrados = {c.id for c in contratistas}
        faltantes = set(datos.contratista_ids) - encontrados
        if faltantes:
            raise HTTPException(
                status_code=404, detail=f"Contratistas no encontrados: {sorted(faltantes)}"
            )
        dados_de_baja = [c.nombre_empresa for c in contratistas if c.dado_de_baja]
        if dados_de_baja:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede convocar a {', '.join(dados_de_baja)}: "
                + ("está dado de baja" if len(dados_de_baja) == 1 else "están dados de baja"),
            )
    else:
        raise HTTPException(
            status_code=422,
            detail="Debés indicar 'contratista_ids' o 'lista_id'",
        )

    if not contratistas:
        raise HTTPException(status_code=422, detail="No hay contratistas para notificar")

    previas = {
        s.contratista_id: s
        for s in db.query(SolicitudPresupuesto).filter(
            SolicitudPresupuesto.reclamo_id == reclamo_id,
            SolicitudPresupuesto.contratista_id.in_([c.id for c in contratistas]),
        )
    }
    if previas and datos.ya_notificados == "preguntar":
        con_presupuesto = {
            contratista_id
            for (contratista_id,) in db.query(Presupuesto.contratista_id).filter(
                Presupuesto.reclamo_id == reclamo_id,
                Presupuesto.contratista_id.in_(previas),
            )
        }
        ya_notificados = [
            ContratistaYaNotificado(
                contratista_id=c.id,
                nombre_empresa=c.nombre_empresa,
                fecha_ultimo_aviso=previas[c.id].fecha_ultimo_aviso,
                presupuesto_cargado=c.id in con_presupuesto,
            ).model_dump(mode="json")
            for c in contratistas
            if c.id in previas
        ]
        raise HTTPException(status_code=409, detail={"ya_notificados": ya_notificados})
    if datos.ya_notificados == "omitir":
        contratistas = [c for c in contratistas if c.id not in previas]
        if not contratistas:
            raise HTTPException(
                status_code=422,
                detail="Todos los contratistas elegidos ya fueron notificados para este reclamo",
            )

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

        # Notificación adicional por email. Sirve tanto para registro normal como
        # Google SSO: en ambos el email queda guardado en el Usuario.
        email_contratista = _email_del_contratista(db, c)
        ok_email = False
        if email_contratista:
            try:
                ok_email = enviar_solicitud_presupuesto(
                    email_contratista,
                    reclamo_id,
                    reclamo.nombre_escuela,
                    reclamo.ubicacion,
                    link,
                )
            except Exception as e:  # noqa: BLE001 - el email es complementario
                print(f"[EMAIL] No se pudo enviar solicitud de presupuesto: {e}")

        # Con que le llegue por un canal ya está convocado: si no, el contratista tiene
        # la invitación en el mail pero el reclamo no le aparece en el portal.
        ok = ok or ok_email
        if ok:
            enviados += 1
            if c.id in previas:
                previas[c.id].fecha_ultimo_aviso = datetime.now(timezone.utc)
            else:
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
    """Lista los contratistas a los que se les solicitó presupuesto para el reclamo y
    todas las ofertas que mandó cada uno. Solo admins.

    Un contratista rechazado puede mandar otra oferta: se devuelve una fila por oferta
    (la más nueva primero) para que las rechazadas no desaparezcan. Si todavía no cargó
    ninguna, va una sola fila pendiente.
    """
    if db.get(Reclamo, reclamo_id) is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    solicitudes = (
        db.query(SolicitudPresupuesto)
        .filter(SolicitudPresupuesto.reclamo_id == reclamo_id)
        .order_by(SolicitudPresupuesto.fecha_solicitud)
        .all()
    )

    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.reclamo_id == reclamo_id)
        .order_by(Presupuesto.id.desc())
        .all()
    )
    presupuestos_por_contratista: dict[int, list[Presupuesto]] = {}
    for p in presupuestos:
        presupuestos_por_contratista.setdefault(p.contratista_id, []).append(p)

    resultado = []
    for s in solicitudes:
        c = s.contratista
        base = dict(
            contratista_id=s.contratista_id,
            nombre_empresa=c.nombre_empresa if c else "—",
            especialidad=c.especialidad if c else "—",
            telefono=c.telefono if c else "—",
            contratista_dado_de_baja=bool(c and c.dado_de_baja),
            fecha_solicitud=s.fecha_solicitud,
        )
        ofertas = presupuestos_por_contratista.get(s.contratista_id, [])
        if not ofertas:
            resultado.append(SolicitudPresupuestoOut(**base, presupuesto_cargado=False))
        for presupuesto in ofertas:
            resultado.append(
                SolicitudPresupuestoOut(
                    **base,
                    presupuesto_cargado=True,
                    presupuesto_id=presupuesto.id,
                    presupuesto_estado=presupuesto.estado.value,
                    presupuesto_fecha=presupuesto.fecha,
                    monto=sum(
                        (i.cantidad * i.costo_unitario for i in presupuesto.items), Decimal("0")
                    ),
                    version=presupuesto.version,
                )
            )
    return resultado


@router.post("/{reclamo_id}/solicitar-informacion", response_model=NotificacionResultado)
def solicitar_informacion(
    reclamo_id: int,
    datos: SolicitarInformacionIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_contratista),
):
    """Un contratista pide información adicional sobre el reclamo.

    El bot reenvía el mensaje por WhatsApp a quien creó el reclamo (telefono_creador).
    """
    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    acceso_reclamos.exigir_acceso(db, reclamo_id, usuario)

    if not reclamo.telefono_creador:
        raise HTTPException(
            status_code=409,
            detail="Este reclamo no fue creado por WhatsApp, no hay un contacto al que reenviar el pedido.",
        )

    # Nombre del contratista que solicita (si tiene ficha vinculada)
    ficha = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    if ficha is not None and ficha.dado_de_baja:
        raise HTTPException(
            status_code=403, detail="Tu ficha de contratista está dada de baja: no podés presupuestar."
        )
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
    usuario: Usuario = Depends(get_current_user),
):
    """Devuelve la coordinación de visita del reclamo (o null si no hay).

    No usa response_model para poder devolver null sin error cuando aún no hay visita.
    """
    from models.visita import Visita
    from schemas.visita import VisitaOut

    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    acceso_reclamos.exigir_acceso(db, reclamo_id, usuario)

    from models.visita import EstadoVisita

    estados_coordinados = {
        EstadoReclamo.VISITA_COORDINADA,
        EstadoReclamo.EN_EJECUCION,
        EstadoReclamo.PENDIENTE_INTERVENCION,
        EstadoReclamo.FINALIZADO,
    }
    if reclamo.estado in estados_coordinados:
        visita = (
            db.query(Visita)
            .filter(Visita.reclamo_id == reclamo_id, Visita.estado == EstadoVisita.CONFIRMADA)
            .order_by(Visita.id.desc())
            .first()
        )
        if visita is None:
            visita = (
                db.query(Visita)
                .filter(Visita.reclamo_id == reclamo_id)
                .order_by(Visita.id.desc())
                .first()
            )
    else:
        visita = (
            db.query(Visita)
            .filter(Visita.reclamo_id == reclamo_id)
            .order_by(Visita.id.desc())
            .first()
        )
    if visita is None:
        return None
    return VisitaOut.model_validate(visita)
