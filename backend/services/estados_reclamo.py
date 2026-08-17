"""Máquina de estados del reclamo.

Toda transición pasa por acá: los endpoints nunca asignan `reclamo.estado` a mano.
Así las reglas viven en un solo lugar y cada cambio queda registrado en el historial.

    PENDIENTE_REVISION ─(se valida)────> PENDIENTE_PRESUPUESTO
                       └─(se descarta)─> RECHAZADO

    PENDIENTE_PRESUPUESTO ─(llega el 1er presupuesto)─> EN_EVALUACION
                          └─(nadie cotizó)───────────> DESIERTO ──> PENDIENTE_PRESUPUESTO

    EN_EVALUACION ─(se aprueba uno)──────> APROBADO ──> EN_EJECUCION ──> FINALIZADO
                  └─(se rechazan todos)─> PENDIENTE_PRESUPUESTO

    CANCELADO: alcanzable desde cualquier estado no terminal.
"""

from sqlalchemy.orm import Session

from models.historial_estado_reclamo import HistorialEstadoReclamo, OrigenCambioEstado
from models.reclamo import EstadoReclamo, Reclamo

ESTADO_INICIAL = EstadoReclamo.PENDIENTE_REVISION

# Estados terminales: el reclamo ya no se mueve más.
ESTADOS_FINALES = frozenset(
    {EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO}
)

# Salidas negativas: sin un motivo escrito no se puede dejar un reclamo acá.
ESTADOS_CON_MOTIVO_OBLIGATORIO = frozenset(
    {EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO, EstadoReclamo.DESIERTO}
)

TRANSICIONES: dict[EstadoReclamo, frozenset[EstadoReclamo]] = {
    EstadoReclamo.PENDIENTE_REVISION: frozenset(
        {
            EstadoReclamo.PENDIENTE_PRESUPUESTO,
            EstadoReclamo.RECHAZADO,
            EstadoReclamo.CANCELADO,
        }
    ),
    EstadoReclamo.PENDIENTE_PRESUPUESTO: frozenset(
        {
            EstadoReclamo.EN_EVALUACION,
            EstadoReclamo.DESIERTO,
            EstadoReclamo.CANCELADO,
        }
    ),
    # Rechazar un presupuesto suelto no mueve el reclamo; volver a
    # PENDIENTE_PRESUPUESTO es para cuando se rechazaron todos.
    EstadoReclamo.EN_EVALUACION: frozenset(
        {
            EstadoReclamo.APROBADO,
            EstadoReclamo.PENDIENTE_PRESUPUESTO,
            EstadoReclamo.CANCELADO,
        }
    ),
    EstadoReclamo.APROBADO: frozenset({EstadoReclamo.EN_EJECUCION, EstadoReclamo.CANCELADO}),
    EstadoReclamo.EN_EJECUCION: frozenset({EstadoReclamo.FINALIZADO, EstadoReclamo.CANCELADO}),
    # Se puede reabrir la convocatoria tras un llamado desierto.
    EstadoReclamo.DESIERTO: frozenset(
        {EstadoReclamo.PENDIENTE_PRESUPUESTO, EstadoReclamo.CANCELADO}
    ),
    EstadoReclamo.FINALIZADO: frozenset(),
    EstadoReclamo.RECHAZADO: frozenset(),
    EstadoReclamo.CANCELADO: frozenset(),
}


class TransicionInvalida(Exception):
    """El cambio de estado pedido no está permitido por la máquina de estados."""


class MotivoRequerido(Exception):
    """El estado destino exige un motivo y no se envió."""


def transiciones_posibles(estado: EstadoReclamo) -> frozenset[EstadoReclamo]:
    return TRANSICIONES[estado]


def puede_transicionar(desde: EstadoReclamo, hacia: EstadoReclamo) -> bool:
    return hacia in TRANSICIONES[desde]


def es_final(estado: EstadoReclamo) -> bool:
    return estado in ESTADOS_FINALES


def registrar_estado_inicial(
    db: Session, reclamo: Reclamo, usuario_id: int | None = None
) -> HistorialEstadoReclamo:
    """Primer asiento del historial, al crearse el reclamo."""
    evento = HistorialEstadoReclamo(
        reclamo=reclamo,
        estado_anterior=None,
        estado_nuevo=reclamo.estado,
        origen=OrigenCambioEstado.MANUAL,
        usuario_id=usuario_id,
        motivo=None,
    )
    db.add(evento)
    return evento


def cambiar_estado(
    db: Session,
    reclamo: Reclamo,
    nuevo_estado: EstadoReclamo,
    motivo: str | None = None,
    usuario_id: int | None = None,
    origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL,
) -> HistorialEstadoReclamo:
    """Mueve el reclamo y deja el asiento en el historial. No hace commit.

    Las transiciones que dispare el propio sistema (ej. al recibirse el primer
    presupuesto) tienen que pasar `origen=AUTOMATICO`.
    """
    estado_anterior = reclamo.estado

    if not puede_transicionar(estado_anterior, nuevo_estado):
        raise TransicionInvalida(
            f"No se puede pasar de {estado_anterior.value} a {nuevo_estado.value}"
        )

    if nuevo_estado in ESTADOS_CON_MOTIVO_OBLIGATORIO and not (motivo or "").strip():
        raise MotivoRequerido(f"Pasar a {nuevo_estado.value} requiere indicar un motivo")

    reclamo.estado = nuevo_estado
    evento = HistorialEstadoReclamo(
        reclamo=reclamo,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        origen=origen,
        usuario_id=usuario_id,
        motivo=(motivo or "").strip() or None,
    )
    db.add(evento)
    return evento
