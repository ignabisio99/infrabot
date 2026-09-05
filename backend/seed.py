"""Carga datos de ejemplo en la base para tener un entorno de desarrollo consistente.

Uso:
    docker compose exec backend python seed.py           # solo si las tablas están vacías
    docker compose exec backend python seed.py --reset    # recrea el schema y recarga todo

`--reset` borra y recrea las tablas a partir de los modelos, así que también sirve para
poner al día una base que quedó desfasada porque un modelo cambió. Deja un admin de
desarrollo listo para entrar (ver ADMIN_EMAIL / ADMIN_PASSWORD).
"""

import logging
import sys

from core.auth import hash_password
from core.database import Base, SessionLocal, engine
from models import (
    Contratista,
    EstadoPresupuesto,
    EstadoReclamo,
    EstadoUsuario,
    HistorialEstadoReclamo,
    ItemPresupuesto,
    OrigenCambioEstado,
    Presupuesto,
    PrioridadReclamo,
    Reclamo,
    TipoUsuario,
    Usuario,
)
from services import estados_presupuesto, estados_reclamo

# Usuario administrador para poder entrar a la app en un entorno recién creado.
# El registro por la UI no sirve para esto: deja la cuenta sin confirmar y esperando
# la aprobación de un admin que en una base nueva no existe.
# Ojo con el dominio: `EmailStr` rechaza los reservados (.local, localhost, example.com),
# así que un admin con esos no podría loguearse aunque el seed lo cree igual.
ADMIN_EMAIL = "admin@infrabot.dev"
ADMIN_PASSWORD = "Admin123!"

# Contraseña común de los contratistas del seed (el email lo trae cada ficha). Sin cuenta
# el portal (/portal/*) no se puede probar: las vistas y los permisos del contratista
# dependen de Contratista.usuario_id.
CONTRATISTA_PASSWORD = "Contra123!"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# `email_cuenta` le da login al contratista. Las dos primeras compiten en el reclamo 1,
# así que con las dos cuentas se puede ver que ninguna accede a la oferta de la otra.
# Belgrano queda sin cuenta a propósito: es el caso de la ficha cargada por mesa de
# entrada que nunca se registró.
CONTRATISTAS = [
    dict(
        nombre_empresa="Electricidad del Sur SRL",
        telefono="011-4555-1234",
        direccion="Av. Rivadavia 4500, CABA",
        especialidad="Electricidad",
        calificacion=4,
        email_cuenta="electricidad@infrabot.dev",
    ),
    dict(
        nombre_empresa="Plomería Integral SA",
        telefono="011-4666-5678",
        direccion="Calle Falsa 123, San Justo",
        especialidad="Plomería",
        calificacion=5,
        email_cuenta="plomeria@infrabot.dev",
    ),
    dict(
        nombre_empresa="Construcciones Belgrano",
        telefono="011-4777-9012",
        direccion="Av. Cabildo 2100, CABA",
        especialidad="Albañilería",
        calificacion=3,
    ),
]

# `camino` son las transiciones que se aplican después de crear el reclamo, para que
# el entorno de desarrollo tenga ejemplos en distintas etapas (y con historial real).
# `origen` por defecto es MANUAL; se marca AUTOMATICO en los cambios que en producción
# va a disparar el sistema y no una persona.
RECLAMOS = [
    dict(
        nombre_escuela="Escuela N°12 - Manuel Belgrano",
        ubicacion="Tablero principal, ala norte",
        prioridad=PrioridadReclamo.ALTA,
        categoria="Electricidad",
        descripcion="Cortocircuito en el tablero principal del ala norte del edificio.",
        observaciones="Se cortó la luz en 3 aulas.",
        camino=[dict(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)],
        presupuestos=[
            dict(
                contratista=0,
                observaciones="Presupuesto para reparación del tablero.",
                items=[
                    dict(descripcion="Mano de obra", cantidad=8, costo_unitario=5000),
                    dict(descripcion="Tablero eléctrico nuevo", cantidad=1, costo_unitario=45000),
                ],
            ),
            dict(
                contratista=1,
                observaciones="Incluye certificación del tablero.",
                items=[
                    dict(descripcion="Mano de obra", cantidad=10, costo_unitario=5200),
                    dict(descripcion="Tablero eléctrico nuevo", cantidad=1, costo_unitario=51000),
                ],
            ),
        ],
    ),
    dict(
        nombre_escuela="Escuela N°5 - Domingo Sarmiento",
        ubicacion="Baño, planta baja",
        prioridad=PrioridadReclamo.MEDIA,
        categoria="Plomería",
        descripcion="Pérdida de agua en el baño de planta baja.",
        observaciones=None,
        camino=[dict(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)],
        presupuestos=[
            dict(
                contratista=1,
                observaciones=None,
                items=[
                    dict(descripcion="Cañería PVC 3/4", cantidad=10, costo_unitario=1200),
                    dict(descripcion="Mano de obra", cantidad=4, costo_unitario=5000),
                ],
                decision=dict(estado=EstadoPresupuesto.APROBADO),
            ),
        ],
        # Al aprobar el presupuesto, el bot ya dejó el reclamo en PENDIENTE_COORDINACION.
        # Para el ejemplo simulamos que se coordinó la visita y arrancó la ejecución.
        camino_posterior=[
            dict(estado=EstadoReclamo.VISITA_COORDINADA, origen=OrigenCambioEstado.AUTOMATICO),
            dict(estado=EstadoReclamo.EN_EJECUCION),
        ],
    ),
    dict(
        nombre_escuela="Escuela N°8 - José de San Martín",
        ubicacion="Patio interno",
        prioridad=PrioridadReclamo.BAJA,
        categoria="Albañilería",
        descripcion="Grieta en la pared del patio interno.",
        observaciones="No representa riesgo inmediato.",
        camino=[],
    ),
    dict(
        nombre_escuela="Escuela N°3 - Bernardino Rivadavia",
        ubicacion="Aula 7, primer piso",
        prioridad=PrioridadReclamo.BAJA,
        categoria="Carpintería",
        descripcion="Pizarrón flojo en el aula 7 del primer piso.",
        observaciones=None,
        camino=[
            dict(estado=EstadoReclamo.RECHAZADO, motivo="Duplicado del reclamo REC-00000002."),
        ],
    ),
    dict(
        nombre_escuela="Escuela N°21 - Juana Azurduy",
        ubicacion="Techo del SUM",
        prioridad=PrioridadReclamo.ALTA,
        categoria="Techos",
        descripcion="Filtraciones en el techo del salón de usos múltiples.",
        observaciones="Se suspendieron actos por goteras.",
        camino=[
            dict(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO),
            dict(
                estado=EstadoReclamo.DESIERTO,
                motivo="Ningún contratista cotizó dentro del plazo de 15 días.",
                origen=OrigenCambioEstado.AUTOMATICO,
            ),
        ],
    ),
]


def reset_schema():
    """Borra y recrea el schema completo a partir de los modelos.

    Borrar sólo las filas no alcanza: `create_all` crea las tablas que faltan pero nunca
    altera las que ya existen, así que si un modelo cambió (una columna nueva, un enum
    nuevo) la base queda desfasada en silencio hasta que una consulta falla. Recrear
    desde cero garantiza que el schema sea exactamente el que describen los modelos, y
    es lo que hace que el reset sirva para todo el equipo sin ALTERs a mano.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def crear_cuentas_de_contratistas(db, contratistas, emails):
    """Vincula cada ficha que declara `email_cuenta` con un usuario que puede entrar."""
    for ficha, email in zip(contratistas, emails):
        if email is None:
            continue
        usuario = Usuario(
            nombre=ficha.nombre_empresa,
            email=email,
            password_hash=hash_password(CONTRATISTA_PASSWORD),
            email_confirmado=True,
            telefono=ficha.telefono,
            direccion=ficha.direccion,
            nombre_empresa=ficha.nombre_empresa,
            especialidad=ficha.especialidad,
            tipo=TipoUsuario.CONTRATISTA,
            estado=EstadoUsuario.APROBADO,
        )
        db.add(usuario)
        db.flush()
        ficha.usuario_id = usuario.id


def crear_admin(db):
    """Crea el admin de desarrollo si no está. Devuelve True si lo creó."""
    if db.query(Usuario).filter(Usuario.email == ADMIN_EMAIL).first() is not None:
        return False

    db.add(
        Usuario(
            nombre="Admin",
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            email_confirmado=True,
            tipo=TipoUsuario.ADMINISTRADOR,
            estado=EstadoUsuario.APROBADO,
        )
    )
    return True


CAMPOS_DEL_RECLAMO = (
    "nombre_escuela",
    "ubicacion",
    "prioridad",
    "categoria",
    "descripcion",
    "observaciones",
)


def _recorrer(db, reclamo, pasos):
    for paso in pasos:
        estados_reclamo.cambiar_estado(
            db,
            reclamo,
            paso["estado"],
            motivo=paso.get("motivo"),
            origen=paso.get("origen", OrigenCambioEstado.MANUAL),
        )


def crear_reclamos(db, contratistas):
    """Arma los reclamos de ejemplo dejando que los estados los decidan los servicios.

    Los pasos manuales están en `camino` (antes de los presupuestos) y `camino_posterior`
    (después). Lo del medio no se escribe: pasar a EN_EVALUACION y a APROBADO lo deduce
    `sincronizar_por_presupuestos` de los presupuestos cargados, igual que en la app. Si
    se escribieran a mano, el seed podría contradecir a las máquinas de estado sin que
    nada avise.
    """
    reclamos = []
    for data in RECLAMOS:
        reclamo = Reclamo(
            **{campo: data[campo] for campo in CAMPOS_DEL_RECLAMO},
            estado=estados_reclamo.ESTADO_INICIAL,
        )
        db.add(reclamo)
        estados_reclamo.registrar_estado_inicial(db, reclamo)
        _recorrer(db, reclamo, data["camino"])

        presupuestos = []
        for datos_presupuesto in data.get("presupuestos", []):
            presupuesto = Presupuesto(
                reclamo=reclamo,
                contratista=contratistas[datos_presupuesto["contratista"]],
                observaciones=datos_presupuesto["observaciones"],
                items=[ItemPresupuesto(**item) for item in datos_presupuesto["items"]],
                estado=estados_presupuesto.ESTADO_INICIAL,
            )
            db.add(presupuesto)
            estados_presupuesto.registrar_estado_inicial(db, presupuesto)
            presupuestos.append((presupuesto, datos_presupuesto.get("decision")))

        # Primero entran todas las ofertas y después se decide, como en la realidad: si
        # se aprobara una con las otras sin cargar, no quedarían NO_SELECCIONADO.
        if presupuestos:
            estados_reclamo.sincronizar_por_presupuestos(db, reclamo)
        for presupuesto, decision in presupuestos:
            if decision is not None:
                estados_presupuesto.decidir(
                    db, presupuesto, decision["estado"], motivo=decision.get("motivo")
                )

        _recorrer(db, reclamo, data.get("camino_posterior", []))
        reclamos.append(reclamo)
    return reclamos


def seed(db):
    # `email_cuenta` no es columna de Contratista: sale acá y se usa para el login.
    emails = [data.get("email_cuenta") for data in CONTRATISTAS]
    contratistas = [
        Contratista(**{k: v for k, v in data.items() if k != "email_cuenta"})
        for data in CONTRATISTAS
    ]
    db.add_all(contratistas)
    db.flush()

    crear_cuentas_de_contratistas(db, contratistas, emails)
    crear_reclamos(db, contratistas)
    db.commit()


def main():
    reiniciar = "--reset" in sys.argv
    if reiniciar:
        logger.info("Recreando el schema desde los modelos...")
        reset_schema()
    else:
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # El admin se asegura siempre, incluso si los datos de ejemplo ya estaban: una
        # base con datos pero sin admin deja la app sin forma de entrar.
        if crear_admin(db):
            db.commit()
            logger.info("Admin creado: %s / %s", ADMIN_EMAIL, ADMIN_PASSWORD)

        if not reiniciar and db.query(Reclamo).first() is not None:
            logger.info("Ya hay datos cargados. Usá --reset si querés borrar todo y recargar.")
            return
        seed(db)
        logger.info("Datos de ejemplo cargados correctamente.")
        for data in CONTRATISTAS:
            if data.get("email_cuenta"):
                logger.info(
                    "Contratista: %s / %s (%s)",
                    data["email_cuenta"],
                    CONTRATISTA_PASSWORD,
                    data["nombre_empresa"],
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
