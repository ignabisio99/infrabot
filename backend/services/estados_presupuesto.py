"""Máquina de estados del presupuesto.

Misma forma que services/estados_reclamo.py: toda transición pasa por acá y cada cambio
queda en el historial.

    RECIBIDO ─(se elige este)──────────> APROBADO
             ├─(no sirve la oferta)────> RECHAZADO
             ├─(hay que corregirla)────> AJUSTES_SOLICITADOS ─(envía la corrección)*─> RECIBIDO
             └─(se aprobó otro)*───────> NO_SELECCIONADO ─(se elige esta)*─> APROBADO

    (*) Las dispara el sistema. Un gestor no marca "no seleccionado": si una oferta no
    le sirve la rechaza. NO_SELECCIONADO puede volver a APROBADO si, tras una
    intervención, se elige una oferta que ya se había enviado.

RECHAZADO cierra esa oferta, pero no al contratista: mientras la convocatoria siga
abierta puede mandar otra, que arranca de cero. Si la oferta sirve pero hay que corregir
algo, se piden ajustes, y cada corrección es una versión nueva del mismo presupuesto.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import (
    EstadoPresupuesto,
    Presupuesto,
    TipoItemPresupuesto,
    VersionPresupuesto,
)
from models.reclamo import EstadoReclamo, Reclamo
from services import estados_reclamo

ESTADO_INICIAL = EstadoPresupuesto.RECIBIDO

# Lo que cuenta como oferta en pie; es lo que mira el reclamo para saber si tiene algo
# para evaluar.
ESTADOS_VIGENTES = frozenset(
    {EstadoPresupuesto.RECIBIDO, EstadoPresupuesto.AJUSTES_SOLICITADOS}
)

# Sin el motivo, el contratista no sabe por qué lo descartaron ni qué corregir.
ESTADOS_CON_MOTIVO_OBLIGATORIO = frozenset(
    {EstadoPresupuesto.RECHAZADO, EstadoPresupuesto.AJUSTES_SOLICITADOS}
)

# Con una de éstas en el reclamo, el contratista no carga otra: la vigente se edita.
ESTADOS_QUE_IMPIDEN_OFERTAR = ESTADOS_VIGENTES

TRANSICIONES: dict[EstadoPresupuesto, frozenset[EstadoPresupuesto]] = {
    EstadoPresupuesto.RECIBIDO: frozenset(
        {
            EstadoPresupuesto.APROBADO,
            EstadoPresupuesto.RECHAZADO,
            EstadoPresupuesto.AJUSTES_SOLICITADOS,
            EstadoPresupuesto.NO_SELECCIONADO,
        }
    ),
    EstadoPresupuesto.AJUSTES_SOLICITADOS: frozenset(
        {
            EstadoPresupuesto.RECIBIDO,
            EstadoPresupuesto.RECHAZADO,
            EstadoPresupuesto.NO_SELECCIONADO,
        }
    ),
    EstadoPresupuesto.APROBADO: frozenset({EstadoPresupuesto.RECHAZADO}),
    EstadoPresupuesto.RECHAZADO: frozenset(),
    EstadoPresupuesto.NO_SELECCIONADO: frozenset({EstadoPresupuesto.APROBADO}),
}

TRANSICIONES_SOLO_AUTOMATICAS: dict[EstadoPresupuesto, frozenset[EstadoPresupuesto]] = {
    EstadoPresupuesto.RECIBIDO: frozenset({EstadoPresupuesto.NO_SELECCIONADO}),
    EstadoPresupuesto.AJUSTES_SOLICITADOS: frozenset(
        {EstadoPresupuesto.RECIBIDO, EstadoPresupuesto.NO_SELECCIONADO}
    ),
    EstadoPresupuesto.APROBADO: frozenset({EstadoPresupuesto.RECHAZADO}),
    EstadoPresupuesto.NO_SELECCIONADO: frozenset({EstadoPresupuesto.APROBADO}),
}


class TransicionInvalida(Exception):
    """El cambio de estado pedido no está permitido por la máquina de estados."""


class MotivoRequerido(Exception):
    """El estado destino exige un motivo y no se envió."""


class EvaluacionNoAbierta(Exception):
    """Se quiso decidir sobre un presupuesto de un reclamo que no está en evaluación."""


def transiciones_posibles(
    estado: EstadoPresupuesto, origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL
) -> frozenset[EstadoPresupuesto]:
    posibles = TRANSICIONES[estado]
    if origen is OrigenCambioEstado.AUTOMATICO:
        return posibles
    return posibles - TRANSICIONES_SOLO_AUTOMATICAS.get(estado, frozenset())


def puede_transicionar(
    desde: EstadoPresupuesto,
    hacia: EstadoPresupuesto,
    origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL,
) -> bool:
    return hacia in transiciones_posibles(desde, origen)


def esta_vigente(presupuesto: Presupuesto) -> bool:
    return presupuesto.estado in ESTADOS_VIGENTES


def hay_evaluacion_abierta(presupuesto: Presupuesto) -> bool:
    """No alcanza con que el presupuesto siga RECIBIDO: si el reclamo se canceló o ya
    eligió otra oferta, sobre ésta no se decide más."""
    return presupuesto.reclamo.estado is EstadoReclamo.EN_EVALUACION


def ofertas_del_contratista(reclamo: Reclamo, contratista_id: int) -> list[Presupuesto]:
    """Las ofertas de un contratista para un reclamo, de la primera a la última.

    Suele haber una sola. Hay más si le rechazaron una y mandó otra, o si quedó sin
    seleccionar y después se reabrió la convocatoria.
    """
    return sorted(
        (p for p in reclamo.presupuestos if p.contratista_id == contratista_id),
        key=lambda p: p.id,
    )


def puede_ofertar(reclamo: Reclamo, contratista_id: int) -> bool:
    """Si el contratista puede cargar una oferta nueva: la convocatoria está abierta y no
    tiene una en evaluación. Una rechazada o sin seleccionar no lo impide."""
    return estados_reclamo.admite_presupuesto(reclamo.estado) and not any(
        p.estado in ESTADOS_QUE_IMPIDEN_OFERTAR
        for p in ofertas_del_contratista(reclamo, contratista_id)
    )


def admite_edicion(presupuesto: Presupuesto) -> bool:
    return esta_vigente(presupuesto) and estados_reclamo.admite_presupuesto(
        presupuesto.reclamo.estado
    )


def _texto(valor: str | None) -> str:
    return (valor or "").strip()


def sin_cambios(
    presupuesto: Presupuesto,
    detalle_tarea: str | None,
    observaciones: str | None,
    items: list[dict],
) -> bool:
    """Si lo que manda el contratista es igual a la versión vigente."""

    def clave(tipo, descripcion, cantidad, unidad, costo_unitario):
        return (
            TipoItemPresupuesto(tipo),
            _texto(descripcion),
            Decimal(cantidad),
            _texto(unidad),
            Decimal(costo_unitario),
        )

    actuales = sorted(
        clave(i.tipo, i.descripcion, i.cantidad, i.unidad, i.costo_unitario)
        for i in presupuesto.items
    )
    nuevos = sorted(clave(**item) for item in items)
    return (
        _texto(presupuesto.detalle_tarea) == _texto(detalle_tarea)
        and _texto(presupuesto.observaciones) == _texto(observaciones)
        and actuales == nuevos
    )


def motivo_estado(presupuesto: Presupuesto) -> str | None:
    """Por qué se rechazó o qué ajustes se pidieron; None en los demás estados."""
    if presupuesto.estado not in ESTADOS_CON_MOTIVO_OBLIGATORIO:
        return None
    return next(
        (
            evento.motivo
            for evento in reversed(presupuesto.historial_estados)
            if evento.estado_nuevo is presupuesto.estado
        ),
        None,
    )


def archivar_version(db: Session, presupuesto: Presupuesto) -> VersionPresupuesto:
    """Guarda el contenido actual antes de que se lo reemplace. No hace commit."""
    anteriores = presupuesto.versiones_anteriores
    version = VersionPresupuesto(
        numero=presupuesto.version,
        detalle_tarea=presupuesto.detalle_tarea,
        observaciones=presupuesto.observaciones,
        items=[
            {
                "tipo": item.tipo.value,
                "descripcion": item.descripcion,
                "cantidad": str(item.cantidad),
                "unidad": item.unidad,
                "costo_unitario": str(item.costo_unitario),
            }
            for item in presupuesto.items
        ],
        fecha_envio=anteriores[-1].fecha_reemplazo if anteriores else presupuesto.fecha,
        ajustes_solicitados=motivo_estado(presupuesto)
        if presupuesto.estado is EstadoPresupuesto.AJUSTES_SOLICITADOS
        else None,
    )
    presupuesto.versiones_anteriores.append(version)
    db.add(version)
    return version


def registrar_estado_inicial(
    db: Session, presupuesto: Presupuesto, usuario_id: int | None = None
) -> HistorialEstadoPresupuesto:
    evento = HistorialEstadoPresupuesto(
        presupuesto=presupuesto,
        estado_anterior=None,
        estado_nuevo=presupuesto.estado,
        origen=OrigenCambioEstado.MANUAL,
        usuario_id=usuario_id,
        motivo=None,
    )
    db.add(evento)
    return evento


def cambiar_estado(
    db: Session,
    presupuesto: Presupuesto,
    nuevo_estado: EstadoPresupuesto,
    motivo: str | None = None,
    usuario_id: int | None = None,
    origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL,
) -> HistorialEstadoPresupuesto:
    """Mueve el presupuesto y deja el asiento en el historial. No hace commit.

    No toca el reclamo: de eso se encarga `decidir`. Están separadas para poder mover los
    hermanos sin re-sincronizar el reclamo una vez por cada uno.
    """
    estado_anterior = presupuesto.estado

    if not puede_transicionar(estado_anterior, nuevo_estado, origen):
        if puede_transicionar(estado_anterior, nuevo_estado, OrigenCambioEstado.AUTOMATICO):
            raise TransicionInvalida(
                f"Pasar de {estado_anterior.value} a {nuevo_estado.value} no se hace a "
                "mano: lo dispara el sistema"
            )
        raise TransicionInvalida(
            f"No se puede pasar de {estado_anterior.value} a {nuevo_estado.value}"
        )

    if nuevo_estado in ESTADOS_CON_MOTIVO_OBLIGATORIO and not (motivo or "").strip():
        raise MotivoRequerido(f"Pasar a {nuevo_estado.value} requiere indicar un motivo")

    presupuesto.estado = nuevo_estado
    evento = HistorialEstadoPresupuesto(
        presupuesto=presupuesto,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        origen=origen,
        usuario_id=usuario_id,
        motivo=(motivo or "").strip() or None,
    )
    db.add(evento)
    return evento


def decidir(
    db: Session,
    presupuesto: Presupuesto,
    nuevo_estado: EstadoPresupuesto,
    motivo: str | None = None,
    usuario_id: int | None = None,
) -> HistorialEstadoPresupuesto:
    """Aplica una decisión y propaga lo que se deduce de ella. No hace commit.

    Es el punto de entrada desde la API porque decidir nunca es sólo sobre este
    presupuesto: aprobar uno deja al resto sin seleccionar y mueve el reclamo.
    """
    reclamo = presupuesto.reclamo
    if not hay_evaluacion_abierta(presupuesto):
        raise EvaluacionNoAbierta(
            f"El reclamo está en {reclamo.estado.value}: no hay una evaluación abierta "
            "en la que decidir"
        )

    evento = cambiar_estado(db, presupuesto, nuevo_estado, motivo=motivo, usuario_id=usuario_id)

    if nuevo_estado is EstadoPresupuesto.APROBADO:
        for hermano in reclamo.presupuestos:
            if hermano.id != presupuesto.id and esta_vigente(hermano):
                cambiar_estado(
                    db,
                    hermano,
                    EstadoPresupuesto.NO_SELECCIONADO,
                    motivo=f"Se aprobó el presupuesto #{presupuesto.id}",
                    origen=OrigenCambioEstado.AUTOMATICO,
                )

    estados_reclamo.sincronizar_por_presupuestos(db, reclamo)

    # Al aprobar un presupuesto, arrancar la coordinación de la visita de trabajo:
    # el bot le pide disponibilidad al contratista ganador.
    if nuevo_estado is EstadoPresupuesto.APROBADO:
        from services import coordinacion_visita

        try:
            coordinacion_visita.iniciar_coordinacion(db, reclamo, presupuesto.contratista)
        except Exception as e:  # noqa: BLE001 - no bloquear la aprobación si falla el aviso
            print(f"[VISITA] No se pudo iniciar la coordinación: {e}")

    return evento
