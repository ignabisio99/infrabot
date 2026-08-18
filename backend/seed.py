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
from datetime import date

from core.auth import hash_password
from core.database import Base, SessionLocal, engine
from models import (
    Contratista,
    EstadoReclamo,
    EstadoUsuario,
    HistorialEstadoReclamo,
    IndiceInflacion,
    ItemPresupuesto,
    OrigenCambioEstado,
    Presupuesto,
    PrioridadReclamo,
    Reclamo,
    ReferenciaCosto,
    TipoUsuario,
    Usuario,
)
from services import estados_reclamo

# Usuario administrador para poder entrar a la app en un entorno recién creado.
# El registro por la UI no sirve para esto: deja la cuenta sin confirmar y esperando
# la aprobación de un admin que en una base nueva no existe.
# Ojo con el dominio: `EmailStr` rechaza los reservados (.local, localhost, example.com),
# así que un admin con esos no podría loguearse aunque el seed lo cree igual.
ADMIN_EMAIL = "admin@infrabot.dev"
ADMIN_PASSWORD = "Admin123!"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CONTRATISTAS = [
    dict(
        nombre_empresa="Electricidad del Sur SRL",
        telefono="011-4555-1234",
        direccion="Av. Rivadavia 4500, CABA",
        especialidad="Electricidad",
        calificacion=4,
    ),
    dict(
        nombre_empresa="Plomería Integral SA",
        telefono="011-4666-5678",
        direccion="Calle Falsa 123, San Justo",
        especialidad="Plomería",
        calificacion=5,
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
        camino=[
            dict(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO),
            dict(estado=EstadoReclamo.EN_EVALUACION, origen=OrigenCambioEstado.AUTOMATICO),
        ],
    ),
    dict(
        nombre_escuela="Escuela N°5 - Domingo Sarmiento",
        ubicacion="Baño, planta baja",
        prioridad=PrioridadReclamo.MEDIA,
        categoria="Plomería",
        descripcion="Pérdida de agua en el baño de planta baja.",
        observaciones=None,
        camino=[
            dict(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO),
            dict(estado=EstadoReclamo.EN_EVALUACION, origen=OrigenCambioEstado.AUTOMATICO),
            dict(estado=EstadoReclamo.APROBADO),
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


# Costos de referencia placeholder (reemplazables por históricos reales del Consejo).
REFERENCIAS_COSTO = [
    dict(
        categoria="Electricidad",
        descripcion="Reparación de tablero eléctrico principal escolar",
        monto_ars=180000,
        fecha_referencia=date(2024, 6, 1),
        unidad="trabajo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Electricidad",
        descripcion="Cambio de cables y tomas en aula",
        monto_ars=95000,
        fecha_referencia=date(2024, 3, 1),
        unidad="aula",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Plomería",
        descripcion="Reparación de pérdida de agua en baño escolar",
        monto_ars=75000,
        fecha_referencia=date(2024, 8, 1),
        unidad="baño",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Plomería",
        descripcion="Reemplazo de cañería PVC y grifería",
        monto_ars=110000,
        fecha_referencia=date(2024, 1, 1),
        unidad="trabajo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Techos",
        descripcion="Reparación de filtraciones y chapas en techo SUM",
        monto_ars=320000,
        fecha_referencia=date(2024, 5, 1),
        unidad="techo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Techos",
        descripcion="Sellado de goteras en aula",
        monto_ars=85000,
        fecha_referencia=date(2023, 11, 1),
        unidad="aula",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Gas",
        descripcion="Revisión y reparación de instalación de gas escolar",
        monto_ars=150000,
        fecha_referencia=date(2024, 4, 1),
        unidad="trabajo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Pintura",
        descripcion="Pintura de aula estándar",
        monto_ars=60000,
        fecha_referencia=date(2024, 2, 1),
        unidad="aula",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Pisos",
        descripcion="Reposición de baldosas en pasillo",
        monto_ars=140000,
        fecha_referencia=date(2024, 7, 1),
        unidad="pasillo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Aberturas",
        descripcion="Cambio de ventana de aula",
        monto_ars=200000,
        fecha_referencia=date(2024, 9, 1),
        unidad="ventana",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Infraestructura",
        descripcion="Reparación de grieta estructural en pared de patio",
        monto_ars=250000,
        fecha_referencia=date(2023, 12, 1),
        unidad="trabajo",
        fuente="seed_placeholder",
    ),
    dict(
        categoria="Otro",
        descripcion="Trabajo general de mantenimiento menor",
        monto_ars=50000,
        fecha_referencia=date(2024, 10, 1),
        unidad="trabajo",
        fuente="seed_placeholder",
    ),
]

# Cache IPC de respaldo (valores ilustrativos; sync real vía /ai/inflacion/sync).
INDICES_INFLACION = [
    dict(periodo="2023-11", indice=100.0, fuente="seed_placeholder"),
    dict(periodo="2023-12", indice=105.0, fuente="seed_placeholder"),
    dict(periodo="2024-01", indice=110.0, fuente="seed_placeholder"),
    dict(periodo="2024-02", indice=115.0, fuente="seed_placeholder"),
    dict(periodo="2024-03", indice=120.0, fuente="seed_placeholder"),
    dict(periodo="2024-04", indice=125.0, fuente="seed_placeholder"),
    dict(periodo="2024-05", indice=130.0, fuente="seed_placeholder"),
    dict(periodo="2024-06", indice=135.0, fuente="seed_placeholder"),
    dict(periodo="2024-07", indice=140.0, fuente="seed_placeholder"),
    dict(periodo="2024-08", indice=145.0, fuente="seed_placeholder"),
    dict(periodo="2024-09", indice=150.0, fuente="seed_placeholder"),
    dict(periodo="2024-10", indice=155.0, fuente="seed_placeholder"),
    dict(periodo="2025-01", indice=170.0, fuente="seed_placeholder"),
    dict(periodo="2025-06", indice=190.0, fuente="seed_placeholder"),
    dict(periodo="2026-01", indice=210.0, fuente="seed_placeholder"),
    dict(periodo="2026-08", indice=230.0, fuente="seed_placeholder"),
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


def crear_reclamos(db):
    """Crea los reclamos y los mueve por la máquina de estados según su `camino`."""
    reclamos = []
    for data in RECLAMOS:
        camino = data["camino"]
        reclamo = Reclamo(
            **{campo: valor for campo, valor in data.items() if campo != "camino"},
            estado=estados_reclamo.ESTADO_INICIAL,
        )
        db.add(reclamo)
        estados_reclamo.registrar_estado_inicial(db, reclamo)
        for paso in camino:
            estados_reclamo.cambiar_estado(
                db,
                reclamo,
                paso["estado"],
                motivo=paso.get("motivo"),
                origen=paso.get("origen", OrigenCambioEstado.MANUAL),
            )
        reclamos.append(reclamo)
    return reclamos


def seed(db):
    contratistas = [Contratista(**data) for data in CONTRATISTAS]
    db.add_all(contratistas)

    reclamos = crear_reclamos(db)
    db.flush()

    db.add(
        Presupuesto(
            reclamo_id=reclamos[0].id,
            contratista_id=contratistas[0].id,
            observaciones="Presupuesto para reparación del tablero.",
            items=[
                ItemPresupuesto(descripcion="Mano de obra", cantidad=8, costo_unitario=5000),
                ItemPresupuesto(descripcion="Tablero eléctrico nuevo", cantidad=1, costo_unitario=45000),
            ],
        )
    )
    db.add(
        Presupuesto(
            reclamo_id=reclamos[1].id,
            contratista_id=contratistas[1].id,
            observaciones=None,
            items=[
                ItemPresupuesto(descripcion="Cañería PVC 3/4", cantidad=10, costo_unitario=1200),
                ItemPresupuesto(descripcion="Mano de obra", cantidad=4, costo_unitario=5000),
            ],
        )
    )

    db.add_all([ReferenciaCosto(**r) for r in REFERENCIAS_COSTO])
    db.add_all([IndiceInflacion(**i) for i in INDICES_INFLACION])
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
    finally:
        db.close()


if __name__ == "__main__":
    main()
