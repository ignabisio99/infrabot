"""Máquina de estados del presupuesto.

Misma forma que services/estados_reclamo.py: toda transición pasa por acá y cada cambio
queda en el historial. El ciclo es corto y de un solo salto.

    RECIBIDO ─(se elige este)──────────> APROBADO
             ├─(no sirve la oferta)────> RECHAZADO
             └─(se aprobó otro)*───────> NO_SELECCIONADO

    (*) Sólo la dispara el sistema, desde `decidir`. Un gestor no marca "no
    seleccionado": si una oferta no le sirve la rechaza, y explica por qué. Quedar sin
    seleccionar es la consecuencia de haber elegido otra, no una opinión sobre ésta.

Los tres estados de salida son terminales. Como el estado del reclamo se deduce de éstos
(ver `estados_reclamo.sincronizar_por_presupuestos`), deshacer una aprobación implicaría
mover el reclamo hacia atrás desde APROBADO, que la otra máquina no permite. Para salir
de un error hay que cancelar el reclamo.
"""

from sqlalchemy.orm import Session

from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo
from services import estados_reclamo

ESTADO_INICIAL = EstadoPresupuesto.RECIBIDO

# Lo que cuenta como oferta en pie; es lo que mira el reclamo para saber si tiene algo
# para evaluar.
ESTADOS_VIGENTES = frozenset({EstadoPresupuesto.RECIBIDO})

# Descartar una oferta sin decir por qué deja al contratista sin respuesta.
ESTADOS_CON_MOTIVO_OBLIGATORIO = frozenset({EstadoPresupuesto.RECHAZADO})

TRANSICIONES: dict[EstadoPresupuesto, frozenset[EstadoPresupuesto]] = {
    EstadoPresupuesto.RECIBIDO: frozenset(
        {
            EstadoPresupuesto.APROBADO,
            EstadoPresupuesto.RECHAZADO,
            EstadoPresupuesto.NO_SELECCIONADO,
        }
    ),
    EstadoPresupuesto.APROBADO: frozenset(),
    EstadoPresupuesto.RECHAZADO: frozenset(),
    EstadoPresupuesto.NO_SELECCIONADO: frozenset(),
}

TRANSICIONES_SOLO_AUTOMATICAS: dict[EstadoPresupuesto, frozenset[EstadoPresupuesto]] = {
    EstadoPresupuesto.RECIBIDO: frozenset({EstadoPresupuesto.NO_SELECCIONADO}),
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
