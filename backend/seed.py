"""Carga datos de ejemplo en la base para tener un entorno de desarrollo consistente.

Uso:
    docker compose exec backend python seed.py           # solo si las tablas están vacías
    docker compose exec backend python seed.py --reset    # recrea el schema y recarga todo

Los costos históricos salen de `data/referencias_costo.csv` y solo se insertan
si todavía no hay una fila con la misma categoría y descripción.

`--reset` borra y recrea las tablas a partir de los modelos, así que también sirve para
poner al día una base que quedó desfasada porque un modelo cambió. Deja un admin de
desarrollo listo para entrar (ver ADMIN_EMAIL / ADMIN_PASSWORD).
"""

import logging
import sys
from decimal import Decimal

import models  # noqa: F401 - registra TODOS los modelos en la metadata antes de create_all
from core.auth import hash_password
from core.database import (
    Base,
    SessionLocal,
    asegurar_columna_detalle_tarea,
    asegurar_columna_pregunta_inicio_enviada,
    asegurar_columna_tipo_item,
    asegurar_tipo_usuario_inspector,
    asegurar_valor_analisis_agente,
    engine,
)
from models import (
    ConfiguracionAuditoria,
    Contratista,
    EstadoPresupuesto,
    EstadoReclamo,
    EstadoUsuario,
    HistorialEstadoReclamo,
    IndiceInflacion,
    ItemPresupuesto,
    OrigenCambioEstado,
    Presupuesto,
    PrioridadReclamo,
    Reclamo,
    TipoItemPresupuesto,
    TipoUsuario,
    Usuario,
)
from models.rol_mano_obra import asegurar_roles_iniciales
from services import estados_presupuesto, estados_reclamo
from services.referencias_costo import cargar_referencias_si_faltan

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

INSPECTOR_EMAIL = "inspector@infrabot.dev"
INSPECTOR_PASSWORD = "Inspector123!"

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
                detalle_tarea="Reemplazo del tablero eléctrico principal y recableado del ala norte.",
                observaciones="Presupuesto para reparación del tablero.",
                items=[
                    dict(
                        tipo=TipoItemPresupuesto.MANO_OBRA,
                        descripcion="Electricista",
                        cantidad=8,
                        unidad="horas",
                        costo_unitario=5000,
                    ),
                    dict(descripcion="Tablero eléctrico nuevo", cantidad=1, costo_unitario=45000),
                ],
            ),
            dict(
                contratista=1,
                detalle_tarea="Reemplazo del tablero y certificación de la instalación.",
                observaciones="Incluye certificación del tablero.",
                items=[
                    dict(
                        tipo=TipoItemPresupuesto.MANO_OBRA,
                        descripcion="Electricista",
                        cantidad=10,
                        unidad="horas",
                        costo_unitario=5200,
                    ),
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
                detalle_tarea="Reparación de la pérdida y reemplazo de tramo de cañería PVC.",
                observaciones=None,
                items=[
                    dict(descripcion="Cañería PVC 3/4", cantidad=10, costo_unitario=1200),
                    dict(
                        tipo=TipoItemPresupuesto.MANO_OBRA,
                        descripcion="Plomero",
                        cantidad=4,
                        unidad="horas",
                        costo_unitario=5000,
                    ),
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


def _crear_usuario_aprobado(db, nombre, email, password, tipo):
    """Crea la cuenta si no está. Devuelve True si la creó."""
    if db.query(Usuario).filter(Usuario.email == email).first() is not None:
        return False

    db.add(
        Usuario(
            nombre=nombre,
            email=email,
            password_hash=hash_password(password),
            email_confirmado=True,
            tipo=tipo,
            estado=EstadoUsuario.APROBADO,
        )
    )
    return True


def crear_admin(db):
    return _crear_usuario_aprobado(
        db, "Admin", ADMIN_EMAIL, ADMIN_PASSWORD, TipoUsuario.ADMINISTRADOR
    )


def crear_inspector(db):
    return _crear_usuario_aprobado(
        db, "Inspector", INSPECTOR_EMAIL, INSPECTOR_PASSWORD, TipoUsuario.INSPECTOR
    )


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
                detalle_tarea=datos_presupuesto.get("detalle_tarea"),
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


# Reclamos "históricos" para que el reporte de métricas tenga datos repartidos en el
# tiempo y con distintos desenlaces. `dias_atras` es cuándo se creó (desde hoy), y
# `dias_resolucion` cuántos días tardó en finalizar (None = sigue abierto en `estado_final`).
RECLAMOS_REPORTE = [
    # Finalizados en distintos meses (alimentan tasa de resolución y días promedio).
    dict(escuela="Escuela N°15 - Rosario Vera", categoria="Plomería", prioridad=PrioridadReclamo.MEDIA, dias_atras=150, dias_resolucion=20),
    dict(escuela="Escuela N°7 - Mariano Moreno", categoria="Electricidad", prioridad=PrioridadReclamo.ALTA, dias_atras=130, dias_resolucion=12),
    dict(escuela="Escuela N°30 - Hipólito Yrigoyen", categoria="Techos", prioridad=PrioridadReclamo.ALTA, dias_atras=110, dias_resolucion=35),
    dict(escuela="Escuela N°9 - Nicolás Avellaneda", categoria="Pintura", prioridad=PrioridadReclamo.BAJA, dias_atras=95, dias_resolucion=8),
    dict(escuela="Escuela N°18 - Esteban Echeverría", categoria="Pisos", prioridad=PrioridadReclamo.MEDIA, dias_atras=80, dias_resolucion=25),
    dict(escuela="Escuela N°2 - Guillermo Rawson", categoria="Plomería", prioridad=PrioridadReclamo.MEDIA, dias_atras=60, dias_resolucion=15),
    dict(escuela="Escuela N°11 - Cornelio Saavedra", categoria="Gas", prioridad=PrioridadReclamo.ALTA, dias_atras=45, dias_resolucion=18),
    dict(escuela="Escuela N°25 - Juan B. Justo", categoria="Aberturas", prioridad=PrioridadReclamo.BAJA, dias_atras=30, dias_resolucion=10),
    # Abiertos (sin resolver), repartidos en el tiempo.
    dict(escuela="Escuela N°14 - Bartolomé Mitre", categoria="Electricidad", prioridad=PrioridadReclamo.ALTA, dias_atras=20, dias_resolucion=None, estado_final=EstadoReclamo.PENDIENTE_PRESUPUESTO),
    dict(escuela="Escuela N°6 - Dalmacio Vélez", categoria="Infraestructura", prioridad=PrioridadReclamo.MEDIA, dias_atras=10, dias_resolucion=None, estado_final=EstadoReclamo.PENDIENTE_REVISION),
    dict(escuela="Escuela N°19 - Juana Manso", categoria="Techos", prioridad=PrioridadReclamo.ALTA, dias_atras=5, dias_resolucion=None, estado_final=EstadoReclamo.PENDIENTE_REVISION),
    dict(escuela="Escuela N°1 - Manuel Dorrego", categoria="Pintura", prioridad=PrioridadReclamo.BAJA, dias_atras=2, dias_resolucion=None, estado_final=EstadoReclamo.PENDIENTE_REVISION),
]


def _seed_reclamos_reporte(db):
    """Crea reclamos con fechas pasadas y desenlaces variados para poblar el reporte.

    A diferencia de RECLAMOS (que muestran el flujo), estos existen para que el reporte
    de métricas tenga volumen, finalizados y distribución temporal. Las fechas de
    creación y de los asientos del historial se backdatean a mano.
    """
    from datetime import datetime, timedelta, timezone

    ahora = datetime.now(timezone.utc)
    for data in RECLAMOS_REPORTE:
        creado = ahora - timedelta(days=data["dias_atras"])
        reclamo = Reclamo(
            nombre_escuela=data["escuela"],
            ubicacion="Sector a definir",
            prioridad=data["prioridad"],
            categoria=data["categoria"],
            descripcion=f"Reclamo de {data['categoria'].lower()} para reporte de prueba.",
            estado=estados_reclamo.ESTADO_INICIAL,
            fecha_creacion=creado,
        )
        db.add(reclamo)
        inicial = estados_reclamo.registrar_estado_inicial(db, reclamo)
        db.flush()
        inicial.fecha = creado

        if data["dias_resolucion"] is not None:
            # Camino completo hasta FINALIZADO. Se backdatea el último asiento a la
            # fecha de resolución para que días-promedio y serie mensual sean realistas.
            resuelto = creado + timedelta(days=data["dias_resolucion"])
            camino = [
                EstadoReclamo.PENDIENTE_PRESUPUESTO,
                EstadoReclamo.EN_EVALUACION,
                EstadoReclamo.APROBADO,
                EstadoReclamo.PENDIENTE_COORDINACION,
                EstadoReclamo.VISITA_COORDINADA,
                EstadoReclamo.EN_EJECUCION,
                EstadoReclamo.FINALIZADO,
            ]
            for i, estado in enumerate(camino):
                origen = (
                    OrigenCambioEstado.AUTOMATICO
                    if estado in (EstadoReclamo.EN_EVALUACION, EstadoReclamo.APROBADO,
                                  EstadoReclamo.PENDIENTE_COORDINACION, EstadoReclamo.VISITA_COORDINADA)
                    else OrigenCambioEstado.MANUAL
                )
                try:
                    evento = estados_reclamo.cambiar_estado(db, reclamo, estado, origen=origen)
                except estados_reclamo.TransicionInvalida:
                    # Si alguna transición no es válida por reglas, se corta el camino.
                    break
                db.flush()
                # Distribuir las fechas de los asientos entre creación y resolución.
                evento.fecha = creado + timedelta(
                    days=data["dias_resolucion"] * (i + 1) / len(camino)
                )
        else:
            estado_final = data.get("estado_final", EstadoReclamo.PENDIENTE_REVISION)
            if estado_final != EstadoReclamo.PENDIENTE_REVISION:
                try:
                    evento = estados_reclamo.cambiar_estado(db, reclamo, estado_final)
                    db.flush()
                    evento.fecha = creado + timedelta(days=1)
                except estados_reclamo.TransicionInvalida:
                    pass
    db.flush()


def seed(db):
    from services.instituciones import cargar_padron_si_vacio

    cargar_padron_si_vacio(db)
    db.commit()

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
    _seed_reclamos_reporte(db)

    creadas_refs = cargar_referencias_si_faltan(db)
    if creadas_refs:
        logger.info("Referencias de costo desde CSV: %d nuevas.", creadas_refs)
    db.add_all([IndiceInflacion(**i) for i in INDICES_INFLACION])
    db.add(
        ConfiguracionAuditoria(
            id=1,
            umbral_aprobar=Decimal("0.05"),
            umbral_revisar=Decimal("0.20"),
        )
    )
    db.flush()

    from services.ai import sync_historicos

    sync_historicos.sync_desde_presupuestos(db)
    db.commit()


def main():
    reiniciar = "--reset" in sys.argv
    if reiniciar:
        logger.info("Recreando el schema desde los modelos...")
        reset_schema()
    else:
        Base.metadata.create_all(bind=engine)
        asegurar_columna_tipo_item()
        asegurar_columna_detalle_tarea()
        asegurar_columna_pregunta_inicio_enviada()
        asegurar_tipo_usuario_inspector()
        asegurar_valor_analisis_agente()

    db = SessionLocal()
    try:
        # El admin se asegura siempre, incluso si los datos de ejemplo ya estaban: una
        # base con datos pero sin admin deja la app sin forma de entrar.
        if crear_admin(db):
            db.commit()
            logger.info("Admin creado: %s / %s", ADMIN_EMAIL, ADMIN_PASSWORD)
        if crear_inspector(db):
            db.commit()
            logger.info("Inspector creado: %s / %s", INSPECTOR_EMAIL, INSPECTOR_PASSWORD)

        asegurar_roles_iniciales(db)

        creadas_refs = cargar_referencias_si_faltan(db)
        if creadas_refs:
            db.commit()
            logger.info("Referencias de costo desde CSV: %d nuevas.", creadas_refs)

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
