"""Máquina de estados del reclamo.

Toda transición pasa por acá: los endpoints nunca asignan `reclamo.estado` a mano.
Así las reglas viven en un solo lugar y cada cambio queda registrado en el historial.

    PENDIENTE_REVISION ─(se valida)────> PENDIENTE_PRESUPUESTO
                       └─(se descarta)─> RECHAZADO

    PENDIENTE_PRESUPUESTO ─(llega el 1er presupuesto)*─> EN_EVALUACION
                          └─(nadie cotizó)────────────> DESIERTO ──> PENDIENTE_PRESUPUESTO

    EN_EVALUACION ─(se aprueba uno)──────────────────> APROBADO ──> EN_EJECUCION ──> FINALIZADO
                  └─(se dio de baja el último)*──────> PENDIENTE_PRESUPUESTO

    CANCELADO: alcanzable desde cualquier estado no terminal.

    (*) Las dos marcadas son exclusivas del sistema (TRANSICIONES_SOLO_AUTOMATICAS):
    las dispara `sincronizar_por_presupuestos` y quedan en el historial con origen
    AUTOMATICO. Son las dos caras del invariante "tiene presupuestos <=> está
    EN_EVALUACION", que es lo que hace que el estado se pueda leer sin ir a contar.

    Todavía no hay forma de decir "ninguna de estas ofertas sirve": los presupuestos no
    tienen estado propio, así que rechazarlos no se puede representar. Mientras tanto no
    hace falta retroceder para pedir más, porque EN_EVALUACION sigue admitiendo que
    lleguen presupuestos nuevos.
"""

from sqlalchemy.orm import Session

from models.historial_estado_reclamo import HistorialEstadoReclamo, OrigenCambioEstado
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo

ESTADO_INICIAL = EstadoReclamo.PENDIENTE_REVISION

# Estados terminales: el reclamo ya no se mueve más.
ESTADOS_FINALES = frozenset(
    {EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO}
)

# En qué estados tiene sentido cargarle un presupuesto al reclamo: ya se validó en la
# revisión inicial y todavía no se eligió contratista. Se admite en EN_EVALUACION
# porque la idea es juntar varias ofertas y recién ahí comparar.
ESTADOS_ADMITEN_PRESUPUESTO = frozenset(
    {EstadoReclamo.PENDIENTE_PRESUPUESTO, EstadoReclamo.EN_EVALUACION}
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
    # La vuelta a PENDIENTE_PRESUPUESTO existe para cuando el reclamo se queda sin
    # presupuestos, y sólo la dispara el sistema (ver TRANSICIONES_SOLO_AUTOMATICAS).
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


# Transiciones que sólo dispara el sistema. Están en TRANSICIONES (son válidas), pero
# `cambiar_estado` las rechaza con origen MANUAL.
#
# Las dos son las que sostienen el invariante "tiene presupuestos <=> está
# EN_EVALUACION", y por eso ninguna persona las decide: las decide el conteo. Moverlas a
# mano dejaría al reclamo describiendo algo que no es (EN_EVALUACION sin nada cargado,
# o PENDIENTE_PRESUPUESTO con presupuestos ahí), y encima haría razonar mal a
# `sincronizar_por_presupuestos`, que asume el invariante: con el estado corrido, una
# baja de presupuesto puede terminar empujando el reclamo hacia EN_EVALUACION.
TRANSICIONES_SOLO_AUTOMATICAS: dict[EstadoReclamo, frozenset[EstadoReclamo]] = {
    EstadoReclamo.PENDIENTE_PRESUPUESTO: frozenset({EstadoReclamo.EN_EVALUACION}),
    EstadoReclamo.EN_EVALUACION: frozenset({EstadoReclamo.PENDIENTE_PRESUPUESTO}),
}


class TransicionInvalida(Exception):
    """El cambio de estado pedido no está permitido por la máquina de estados."""


class MotivoRequerido(Exception):
    """El estado destino exige un motivo y no se envió."""


class ReclamoNoAdmitePresupuesto(Exception):
    """El reclamo está en un estado donde no corresponde cargarle presupuestos."""


def transiciones_posibles(
    estado: EstadoReclamo, origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL
) -> frozenset[EstadoReclamo]:
    """Destinos válidos desde `estado`.

    Por defecto los que puede elegir una persona, que es lo que necesita la UI. El
    sistema (AUTOMATICO) suma los de TRANSICIONES_SOLO_AUTOMATICAS.
    """
    posibles = TRANSICIONES[estado]
    if origen is OrigenCambioEstado.AUTOMATICO:
        return posibles
    return posibles - TRANSICIONES_SOLO_AUTOMATICAS.get(estado, frozenset())


def puede_transicionar(
    desde: EstadoReclamo,
    hacia: EstadoReclamo,
    origen: OrigenCambioEstado = OrigenCambioEstado.MANUAL,
) -> bool:
    return hacia in transiciones_posibles(desde, origen)


def es_final(estado: EstadoReclamo) -> bool:
    return estado in ESTADOS_FINALES


def admite_presupuesto(estado: EstadoReclamo) -> bool:
    return estado in ESTADOS_ADMITEN_PRESUPUESTO


def validar_admite_presupuesto(reclamo: Reclamo) -> None:
    """Corta antes de cargarle o editarle un presupuesto a un reclamo que no lo admite."""
    if not admite_presupuesto(reclamo.estado):
        raise ReclamoNoAdmitePresupuesto(
            f"El reclamo está en {reclamo.estado.value} y no admite presupuestos"
        )


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


def sincronizar_por_presupuestos(db: Session, reclamo: Reclamo) -> HistorialEstadoReclamo | None:
    """Acomoda el estado del reclamo según tenga o no presupuestos cargados.

    Se llama al crear y al dar de baja un presupuesto. Devuelve el asiento del historial
    si hubo cambio, o None si el estado ya era el que corresponde (por ejemplo, el
    segundo presupuesto de un reclamo que ya está EN_EVALUACION).

    No hace commit, pero sí `flush`: la sesión está configurada con autoflush=False,
    así que sin esto el INSERT o el DELETE recién hecho todavía no se vería en el conteo.
    """
    db.flush()
    tiene_presupuestos = (
        db.query(Presupuesto.id).filter(Presupuesto.reclamo_id == reclamo.id).first() is not None
    )

    # Los motivos describen la condición que se observó y no el evento que la causó
    # ("llegó un presupuesto", "se dio de baja el último"): la función ve el conteo, no
    # el disparador, así que contar un evento sería adivinar.
    #
    # El usuario queda en None a propósito: un cambio AUTOMATICO no tiene una persona
    # detrás, y el `origen` del historial ya cuenta que lo disparó el sistema.
    if tiene_presupuestos and reclamo.estado == EstadoReclamo.PENDIENTE_PRESUPUESTO:
        return cambiar_estado(
            db,
            reclamo,
            EstadoReclamo.EN_EVALUACION,
            motivo="El reclamo ya tiene presupuestos para evaluar",
            origen=OrigenCambioEstado.AUTOMATICO,
        )

    if not tiene_presupuestos and reclamo.estado == EstadoReclamo.EN_EVALUACION:
        return cambiar_estado(
            db,
            reclamo,
            EstadoReclamo.PENDIENTE_PRESUPUESTO,
            motivo="El reclamo se quedó sin presupuestos",
            origen=OrigenCambioEstado.AUTOMATICO,
        )

    return None
