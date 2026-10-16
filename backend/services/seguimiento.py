"""Recordatorios a contratistas por WhatsApp si un reclamo en ejecución lleva demasiado sin aviso (CU-05)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from core import reloj
from core.whatsapp_client import enviar_mensaje
from models.comentario_reclamo import ComentarioReclamo
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.historial_estado_reclamo import OrigenCambioEstado
from models.recordatorio_contratista import RecordatorioContratista
from services import estados_reclamo

logger = logging.getLogger(__name__)

MARCA_INTERVENCION = "Pendiente de intervención"
# Textos viejos que todavía pueden estar en observaciones.
_MARCAS_INTERVENCION = (MARCA_INTERVENCION, "[CU-05] Pendiente de intervención")
MAX_INTENTOS_DEFAULT = 5

# Reclamos con presupuesto ya elegido: se puede saltar a intervención para probar.
ESTADOS_SALTO_INTERVENCION = frozenset(
    {
        EstadoReclamo.APROBADO,
        EstadoReclamo.PENDIENTE_COORDINACION,
        EstadoReclamo.VISITA_COORDINADA,
        EstadoReclamo.EN_EJECUCION,
    }
)


class IntervencionNoForzable(Exception):
    """Este reclamo no se puede pasar a pendiente de intervención de una."""


def seguimiento_horas() -> float:
    # 6 h: a las 6 horas de entrar en ejecución se pregunta por primera vez si terminó.
    # Después el ritmo lo marca el tiempo estimado que informa el contratista.
    try:
        return float(os.getenv("SEGUIMIENTO_HORAS") or "6")
    except ValueError:
        return 6.0


def seguimiento_intervalo_segundos() -> int:
    try:
        return int(os.getenv("SEGUIMIENTO_INTERVALO_SEGUNDOS") or "900")
    except ValueError:
        return 900


def seguimiento_max_intentos() -> int:
    try:
        return max(1, int(os.getenv("SEGUIMIENTO_MAX_INTENTOS") or str(MAX_INTENTOS_DEFAULT)))
    except ValueError:
        return MAX_INTENTOS_DEFAULT


@dataclass(frozen=True)
class ResultadoSeguimiento:
    enviados: int
    omitidos: int
    escalados: int = 0
    detalles: list[dict] = field(default_factory=list)


def ejecutar_seguimiento(db: Session) -> ResultadoSeguimiento:
    """Envía recordatorio si pasaron SEGUIMIENTO_HORAS desde el último aviso (o desde EN_EJECUCION)."""
    umbral = timedelta(hours=seguimiento_horas())
    ahora = reloj.ahora()
    reclamos = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.historial_estados))
        .filter(Reclamo.estado == EstadoReclamo.EN_EJECUCION)
        .all()
    )
    enviados = 0
    omitidos = 0
    escalados = 0
    detalles: list[dict] = []
    for reclamo in reclamos:
        # Marca de intervención forzada por el admin (herramienta de simulación): sigue
        # yendo a PENDIENTE_INTERVENCION, no a DESIERTO.
        if tiene_marca_intervencion(reclamo.observaciones):
            if _escalar(db, reclamo):
                escalados += 1
                detalles.append({
                    "tipo": "intervencion",
                    "reclamo_id": reclamo.id,
                    "detalle": f"⚠️ Reclamo #{reclamo.id} escalado a intervención forzada",
                })
            else:
                omitidos += 1
            continue
        if _vencer(db, reclamo, ahora, umbral):
            resultado_envio = _enviar(db, reclamo, ahora)
            if resultado_envio is True:
                enviados += 1
                detalles.append({
                    "tipo": "pregunta_termino",
                    "reclamo_id": reclamo.id,
                    "detalle": f"❓ Pregunta de seguimiento ('¿Terminaste el trabajo?') enviada al contratista del Reclamo #{reclamo.id}",
                })
                # Agotados los intentos sin respuesta: el reclamo queda desierto para
                # poder reconvocar (CU-05: el contratista dejó de responder).
                if _requiere_intervencion(db, reclamo.id):
                    if _escalar_desierto(db, reclamo):
                        escalados += 1
                        detalles.append({
                            "tipo": "desierto",
                            "reclamo_id": reclamo.id,
                            "detalle": f"⚠️ Reclamo #{reclamo.id} pasó a desierto por falta de respuesta del contratista",
                        })
            else:
                omitidos += 1
        else:
            omitidos += 1
    return ResultadoSeguimiento(enviados=enviados, omitidos=omitidos, escalados=escalados, detalles=detalles)


def _vencer(db: Session, reclamo: Reclamo, ahora: datetime, umbral: timedelta) -> bool:
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila and (fila.cantidad_envios or 0) >= seguimiento_max_intentos():
        return False
    if tiene_marca_intervencion(reclamo.observaciones):
        return False
    # Si ya se le preguntó a la escuela si quedó resuelto, el contratista no se molesta.
    if fila and fila.consulto_escuela:
        return False
    # Si el contratista dio un tiempo estimado, la próxima pregunta se rige por esa fecha
    # y no por el umbral fijo de 6 h.
    if fila and fila.proxima_pregunta is not None:
        prox = fila.proxima_pregunta
        if prox.tzinfo is None:
            prox = prox.replace(tzinfo=timezone.utc)
        return ahora >= prox
    referencia = fila.ultimo_envio if fila else _fecha_en_ejecucion(reclamo)
    if referencia is None:
        referencia = reclamo.fecha_creacion
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    return ahora - referencia >= umbral


def _fecha_en_ejecucion(reclamo: Reclamo):
    for evento in reversed(reclamo.historial_estados or []):
        if evento.estado_nuevo == EstadoReclamo.EN_EJECUCION:
            return evento.fecha
    return reclamo.fecha_creacion


def _enviar(db: Session, reclamo: Reclamo, ahora: datetime) -> bool:
    presupuesto = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.contratista))
        .filter(Presupuesto.reclamo_id == reclamo.id)
        .order_by(Presupuesto.fecha.desc())
        .first()
    )
    if presupuesto is None or presupuesto.contratista is None:
        logger.info("Seguimiento reclamo %s: sin contratista", reclamo.id)
        return False

    telefono = _normalizar_telefono(presupuesto.contratista.telefono)
    if not telefono:
        logger.info("Seguimiento reclamo %s: teléfono inválido", reclamo.id)
        return False

    cuerpo = (
        f"Hola {presupuesto.contratista.nombre_empresa}, "
        f"el reclamo #{reclamo.id} ({reclamo.nombre_escuela}) está en ejecución.\n\n"
        "¿Terminaste el trabajo?"
    )
    try:
        from core.whatsapp_client import enviar_botones
        from services import cu05_botones

        enviar_botones(
            telefono,
            cuerpo,
            [
                {"id": cu05_botones.TERMINO_SI, "title": "Sí, terminé"},
                {"id": cu05_botones.TERMINO_NO, "title": "Todavía no"},
            ],
        )
    except Exception:
        logger.exception("No se pudo enviar recordatorio del reclamo %s", reclamo.id)
        return False

    from core.whatsapp_handler import registrar_estado_conversacion

    registrar_estado_conversacion(
        telefono,
        {"paso": "cu05_termino", "reclamo_id": reclamo.id},
    )

    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila is None:
        db.add(
            RecordatorioContratista(
                reclamo_id=reclamo.id,
                ultimo_envio=ahora,
                cantidad_envios=1,
            )
        )
    else:
        fila.ultimo_envio = ahora
        fila.cantidad_envios = (fila.cantidad_envios or 0) + 1
        # Al re-preguntar se consume el estimado anterior: vuelve a regir el umbral/estimado nuevo.
        fila.proxima_pregunta = None
    db.flush()
    return True


def _requiere_intervencion(db: Session, reclamo_id: int) -> bool:
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo_id)
        .first()
    )
    return bool(fila and (fila.cantidad_envios or 0) >= seguimiento_max_intentos())


def tiene_marca_intervencion(observaciones: str | None) -> bool:
    obs = observaciones or ""
    return any(m in obs for m in _MARCAS_INTERVENCION)


def quitar_lineas_marca_intervencion(observaciones: str | None) -> str | None:
    if not tiene_marca_intervencion(observaciones):
        return observaciones or None
    limpio = "\n".join(
        ln for ln in (observaciones or "").splitlines()
        if not any(m in ln for m in _MARCAS_INTERVENCION)
    ).strip()
    return limpio or None


def reiniciar_reloj_seguimiento(db: Session, reclamo: Reclamo) -> None:
    """Al volver a ejecución, el umbral de 48 h arranca de nuevo."""
    ahora = reloj.ahora()
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila is None:
        db.add(
            RecordatorioContratista(
                reclamo_id=reclamo.id,
                ultimo_envio=ahora,
                cantidad_envios=0,
            )
        )
        return
    fila.ultimo_envio = ahora
    fila.cantidad_envios = 0


def forzar_intervencion(db: Session, reclamo: Reclamo) -> bool:
    """Pasa el reclamo a pendiente de intervención sin esperar los 5 avisos.

    Si todavía no está en ejecución (aprobado o visita), salta esos pasos. Hace falta
    un presupuesto aprobado.
    """
    if reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION:
        return False
    if reclamo.estado not in ESTADOS_SALTO_INTERVENCION:
        raise IntervencionNoForzable(
            "Elegí un reclamo con presupuesto aprobado (aprobado, visita o en ejecución)"
        )
    aprobado = (
        db.query(Presupuesto)
        .filter(
            Presupuesto.reclamo_id == reclamo.id,
            Presupuesto.estado == EstadoPresupuesto.APROBADO,
        )
        .first()
    )
    if aprobado is None:
        raise IntervencionNoForzable("Ese reclamo no tiene un presupuesto aprobado")
    _llevar_a_ejecucion(db, reclamo)
    return _escalar(db, reclamo)


def _llevar_a_ejecucion(db: Session, reclamo: Reclamo) -> None:
    """Salta coordinación/visita para poder simular la falta de respuesta."""
    motivo = "Simulación: se salta a ejecución para probar la intervención"
    pasos = (
        (EstadoReclamo.APROBADO, EstadoReclamo.PENDIENTE_COORDINACION, OrigenCambioEstado.AUTOMATICO),
        (
            EstadoReclamo.PENDIENTE_COORDINACION,
            EstadoReclamo.VISITA_COORDINADA,
            OrigenCambioEstado.AUTOMATICO,
        ),
        (EstadoReclamo.VISITA_COORDINADA, EstadoReclamo.EN_EJECUCION, OrigenCambioEstado.MANUAL),
    )
    for desde, hacia, origen in pasos:
        if reclamo.estado == desde:
            estados_reclamo.cambiar_estado(
                db, reclamo, hacia, motivo=motivo, origen=origen
            )


def _escalar(db: Session, reclamo: Reclamo) -> bool:
    """Tras 5 avisos sin respuesta: pasa a Pendiente de intervención."""
    if reclamo.estado != EstadoReclamo.EN_EJECUCION:
        return False
    motivo = (
        f"El contratista no respondió {seguimiento_max_intentos()} "
        "recordatorios de avance."
    )
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.PENDIENTE_INTERVENCION,
        motivo=motivo,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    reclamo.observaciones = quitar_lineas_marca_intervencion(reclamo.observaciones)
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto=f"[Sistema]\nPendiente de intervención: {motivo} Reasignar o contactarlo.",
        )
    )
    logger.warning("Reclamo %s: pendiente de intervención (sin respuesta del contratista)", reclamo.id)
    db.flush()
    return True


def _escalar_desierto(db: Session, reclamo: Reclamo) -> bool:
    """Tras los intentos máximos sin respuesta del contratista: EN_EJECUCION -> DESIERTO.

    A diferencia de _escalar (intervención, forzada por el admin), este es el camino
    automático del seguimiento cuando el contratista dejó de contestar las preguntas de
    avance. Deja el reclamo listo para reconvocar.
    """
    if reclamo.estado != EstadoReclamo.EN_EJECUCION:
        return False
    motivo = (
        f"El contratista no respondió {seguimiento_max_intentos()} "
        "preguntas de avance. Se reconvoca."
    )
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.DESIERTO,
        motivo=motivo,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto=f"[Sistema]\nDesierto: {motivo}",
        )
    )
    logger.warning("Reclamo %s: desierto (sin respuesta del contratista)", reclamo.id)
    db.flush()
    return True


# --- CU-05 pieza 2: respuestas del contratista a la pregunta "¿terminaste?" ------------


def _horas_estimadas(texto: str) -> float | None:
    """Interpreta un tiempo estimado libre a horas. Ej: '2 días' -> 48, '5 horas' -> 5.

    Si no encuentra número, devuelve None (se usa un fallback). Reconoce días/horas/minutos
    y 'semana(s)'. Si hay número sin unidad, se asume en horas.
    """
    t = (texto or "").strip().lower()
    m = re.search(r"(\d+(?:[.,]\d+)?)", t)
    if not m:
        return None
    valor = float(m.group(1).replace(",", "."))
    if re.search(r"semana", t):
        return valor * 24 * 7
    if re.search(r"d[ií]a", t):
        return valor * 24
    if re.search(r"min", t):
        return valor / 60
    # "hora", "hs", "h" o sin unidad: horas.
    return valor


def registrar_tiempo_estimado(db: Session, reclamo: Reclamo, texto: str) -> float:
    """El contratista dijo cuánto le falta. Programa la próxima pregunta a esa altura.

    Devuelve las horas estimadas (interpretadas). Si no se pudo interpretar, usa el
    umbral por defecto de seguimiento como fallback.
    """
    ahora = reloj.ahora()
    horas = _horas_estimadas(texto)
    if horas is None or horas <= 0:
        horas = seguimiento_horas()
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    proxima = ahora + timedelta(hours=horas)
    if fila is None:
        db.add(
            RecordatorioContratista(
                reclamo_id=reclamo.id,
                ultimo_envio=ahora,
                cantidad_envios=1,
                proxima_pregunta=proxima,
            )
        )
    else:
        fila.proxima_pregunta = proxima
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto=f"[WhatsApp — Contratista]\nTiempo estimado restante informado: {texto.strip()}",
        )
    )
    db.commit()
    return horas


def preguntar_a_escuela_si_resuelto(db: Session, reclamo: Reclamo) -> bool:
    """El contratista confirmó que terminó: se le pregunta a la escuela si quedó resuelto.

    Marca consulto_escuela para no seguir molestando al contratista. El reclamo sigue en
    EN_EJECUCION hasta que la escuela confirme (ver resolucion_escuela).
    """
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    ahora = reloj.ahora()
    if fila is None:
        fila = RecordatorioContratista(
            reclamo_id=reclamo.id, ultimo_envio=ahora, cantidad_envios=0
        )
        db.add(fila)
    fila.consulto_escuela = True
    fila.proxima_pregunta = None

    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto="[WhatsApp — Contratista]\nEl contratista informó que terminó el trabajo.",
        )
    )
    db.commit()

    if not reclamo.telefono_creador:
        return False

    from core.whatsapp_handler import registrar_estado_conversacion
    from core.whatsapp_client import enviar_botones
    from services import cu05_botones

    registrar_estado_conversacion(
        reclamo.telefono_creador,
        {"paso": "cu05_resuelto", "reclamo_id": reclamo.id},
    )
    try:
        enviar_botones(
            reclamo.telefono_creador,
            f"🔧 *Reclamo #{reclamo.id} — {reclamo.nombre_escuela}*\n\n"
            "El contratista informó que terminó el trabajo.\n"
            "¿Nos confirmás que el problema quedó resuelto?",
            [
                {"id": cu05_botones.RESUELTO_SI, "title": "Sí, resuelto"},
                {"id": cu05_botones.RESUELTO_NO, "title": "No del todo"},
            ],
        )
    except Exception:
        logger.exception("No se pudo preguntar a la escuela del reclamo %s", reclamo.id)
        return False
    return True


def reactivar_seguimiento(db: Session, reclamo: Reclamo) -> None:
    """La escuela dijo que NO quedó resuelto: se reactiva el ciclo de preguntas al contratista."""
    ahora = reloj.ahora()
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila is None:
        db.add(
            RecordatorioContratista(
                reclamo_id=reclamo.id, ultimo_envio=ahora, cantidad_envios=0
            )
        )
        return
    fila.consulto_escuela = False
    fila.cantidad_envios = 0
    fila.ultimo_envio = ahora
    fila.proxima_pregunta = None


def _normalizar_telefono(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if not digitos:
        return ""
    if digitos.startswith("54"):
        return digitos
    if digitos.startswith("0"):
        digitos = digitos.lstrip("0")
    if len(digitos) == 10:
        return "54" + digitos
    return digitos
