"""Carga datos de ejemplo en la base para tener un entorno de desarrollo consistente.

Uso:
    docker compose exec backend python seed.py           # solo si las tablas están vacías
    docker compose exec backend python seed.py --reset    # recrea el schema y recarga todo

Los costos históricos salen de `data/referencias_costo.csv`. Cada corrida
inserta filas nuevas, actualiza las de la misma categoría y descripción, y
apaga las que este CSV ya no trae. No toca las que vinieron de un presupuesto.

`--reset` borra y recrea las tablas a partir de los modelos, así que también sirve para
poner al día una base que quedó desfasada porque un modelo cambió. Deja un admin de
desarrollo listo para entrar (ver ADMIN_EMAIL / ADMIN_PASSWORD).
"""

import logging
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import models  # noqa: F401 - registra TODOS los modelos en la metadata antes de create_all
from core import reloj, whatsapp_client
from core.auth import hash_password
from core.database import (
    Base,
    SessionLocal,
    asegurar_columna_autor_foto,
    asegurar_columna_detalle_tarea,
    asegurar_columna_tipo_item,
    asegurar_columnas_seguimiento,
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
    EstadoVisita,
    HistorialEstadoReclamo,
    IndiceInflacion,
    Institucion,
    ItemPresupuesto,
    OrigenCambioEstado,
    Presupuesto,
    PrioridadReclamo,
    Reclamo,
    SolicitudPresupuesto,
    TipoItemPresupuesto,
    TipoUsuario,
    Usuario,
    Visita,
)
from models.recordatorio_contratista import RecordatorioContratista
from models.rol_mano_obra import asegurar_roles_iniciales
from services import coordinacion_visita, estados_presupuesto, estados_reclamo
from services.referencias_costo import cargar_referencias_si_faltan, sincronizar_desde_csv

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
        institucion="060584200",  # EP Nº10 Estados Unidos de Norteamérica
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
        institucion="060829300",  # EP Nº5 Ingeniero Jorge Newbery
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
        # A este número (simulado, nunca sale a Meta) el bot le manda los horarios para
        # elegir. Sirve también para seguir la charla desde el simulador de WhatsApp.
        telefono_creador="sim5491100000002",
        # La visita queda acordada para dentro de 3 días a las 10: los recordatorios y la
        # pregunta de inicio de obra se pueden ver adelantando el simulador de tiempo.
        visita=dict(dias_adelante=3, hora=10),
    ),
    dict(
        institucion="060746900",  # ES Nº1 Perito Moreno
        prioridad=PrioridadReclamo.BAJA,
        categoria="Albañilería",
        descripcion="Grieta en la pared del patio interno.",
        observaciones="No representa riesgo inmediato.",
        camino=[],
    ),
    dict(
        institucion="060480000",  # EP Nº3 Bartolomé Mitre
        prioridad=PrioridadReclamo.BAJA,
        categoria="Carpintería",
        descripcion="Pizarrón flojo en el aula 7 del primer piso.",
        observaciones=None,
        camino=[
            dict(estado=EstadoReclamo.RECHAZADO, motivo="Duplicado del reclamo REC-00000002."),
        ],
    ),
    dict(
        institucion="061154700",  # EEST Nº5 Galileo Galilei
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
    "prioridad",
    "categoria",
    "descripcion",
    "observaciones",
)


def _escuela_del_padron(db, identificador):
    """Nombre y ubicación tal como los deja el bot al elegir una escuela del padrón.

    La ubicación del reclamo es la dirección de la escuela; el aula o sector va en la
    descripción. `identificador` es el oficial del CSV, que no cambia entre cargas.
    """
    institucion = db.query(Institucion).filter_by(identificador=identificador).one()
    return {
        "nombre_escuela": " ".join(institucion.nombre.split()),
        "ubicacion": " ".join((institucion.domicilio or "").split()),
    }


def _coordinar_visita(db, reclamo, dias_adelante, hora):
    """Coordina la visita por el mismo camino que el bot: el contratista propone dos
    horarios y la escuela elige el primero. El reclamo queda en VISITA_COORDINADA.
    """
    visita = db.query(Visita).filter_by(reclamo_id=reclamo.id).one()
    # En hora argentina, como la escribe el contratista y la interpreta el bot.
    primera = (reloj.ahora_art() + timedelta(days=dias_adelante)).replace(
        hour=hora, minute=0, second=0, microsecond=0
    )
    # Los domingos no se trabaja: ninguna de las opciones puede caer en uno.
    if primera.weekday() == 6:
        primera += timedelta(days=1)
    segunda = primera + timedelta(days=2 if primera.weekday() == 5 else 1)
    opciones = [primera, segunda]
    coordinacion_visita.agregar_disponibilidad(
        db, visita, ", ".join(f.strftime("%d/%m %H:%M") for f in opciones)
    )
    enviada, motivo = coordinacion_visita.finalizar_disponibilidad(db, visita)
    if not enviada:
        raise RuntimeError(f"No se pudo coordinar la visita del reclamo {reclamo.id}: {motivo}")
    coordinacion_visita.confirmar_eleccion(db, visita, 1)


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

    Los pasos manuales están en `camino` (antes de los presupuestos) y, después de
    aprobar, `visita`. Lo del medio no se escribe: pasar a EN_EVALUACION y a
    APROBADO lo deduce `sincronizar_por_presupuestos` de los presupuestos cargados, igual
    que en la app. Si se escribieran a mano, el seed podría contradecir a las máquinas de
    estado sin que nada avise.
    """
    reclamos = []
    for data in RECLAMOS:
        reclamo = Reclamo(
            **{campo: data[campo] for campo in CAMPOS_DEL_RECLAMO},
            **_escuela_del_padron(db, data["institucion"]),
            telefono_creador=data.get("telefono_creador"),
            estado=estados_reclamo.ESTADO_INICIAL,
        )
        db.add(reclamo)
        estados_reclamo.registrar_estado_inicial(db, reclamo)
        _recorrer(db, reclamo, data["camino"])

        # La pestaña Presupuestos del reclamo y "Mis solicitudes" del portal listan
        # solicitudes, no presupuestos: sin la solicitud, la oferta no aparece en ninguna.
        db.flush()
        presupuestos = []
        for datos_presupuesto in data.get("presupuestos", []):
            contratista = contratistas[datos_presupuesto["contratista"]]
            db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=contratista.id))
            presupuesto = Presupuesto(
                reclamo=reclamo,
                contratista=contratista,
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

        if "visita" in data:
            _coordinar_visita(db, reclamo, **data["visita"])
        reclamos.append(reclamo)

    db.flush()
    rng = random.Random(len(RECLAMOS))
    for reclamo in reclamos:
        _escalonar_fechas(db, reclamo, rng)
    db.commit()
    return reclamos


def _escalonar_fechas(db, reclamo, rng):
    """Reparte en los días previos lo que los servicios acaban de registrar.

    Los servicios fechan todo en el momento de la llamada, así que estos reclamos
    quedarían cargados, presupuestados, aprobados y coordinados en el mismo segundo.
    Se corren hacia atrás manteniendo el orden: un día o dos entre los pasos de una
    persona, el mismo momento para lo que el sistema dispara al aprobar, y los 15 días
    de plazo antes de un DESIERTO.
    """
    eventos = (
        db.query(HistorialEstadoReclamo)
        .filter_by(reclamo_id=reclamo.id)
        .order_by(HistorialEstadoReclamo.id)
        .all()
    )
    saltos = []
    for evento in eventos[1:]:
        if evento.estado_nuevo is EstadoReclamo.PENDIENTE_COORDINACION:
            saltos.append(timedelta(minutes=1))
        elif evento.estado_nuevo is EstadoReclamo.DESIERTO:
            saltos.append(timedelta(days=15))
        else:
            saltos.append(timedelta(days=rng.randint(1, 2), hours=rng.randint(0, 4)))

    fecha = reloj.ahora() - timedelta(hours=rng.randint(2, 6)) - sum(saltos, timedelta())
    reclamo.fecha_creacion = eventos[0].fecha = fecha
    fechas = {}
    for evento, salto in zip(eventos[1:], saltos):
        fecha += salto
        evento.fecha = fecha
        fechas[evento.estado_nuevo] = fecha

    revisado = fechas.get(EstadoReclamo.PENDIENTE_PRESUPUESTO)
    if revisado is not None:
        for solicitud in db.query(SolicitudPresupuesto).filter_by(reclamo_id=reclamo.id):
            solicitud.fecha_solicitud = solicitud.fecha_ultimo_aviso = revisado + timedelta(hours=1)

    primera_oferta = fechas.get(EstadoReclamo.EN_EVALUACION)
    aprobado = fechas.get(EstadoReclamo.APROBADO)
    for i, presupuesto in enumerate(reclamo.presupuestos):
        presupuesto.fecha = primera_oferta + timedelta(hours=3 * i)
        for evento in presupuesto.historial_estados:
            evento.fecha = presupuesto.fecha if evento.estado_anterior is None else aprobado

    coordinacion = fechas.get(EstadoReclamo.PENDIENTE_COORDINACION)
    if coordinacion is not None:
        for visita in db.query(Visita).filter_by(reclamo_id=reclamo.id):
            visita.fecha_creacion = coordinacion


# ---------------------------------------------------------------------------------------
# Reclamos históricos
#
# Volumen para el calendario, el dashboard y los reportes. Cubren del primer día del mes
# pasado al último del mes que viene (con el seed corrido en noviembre: octubre a
# diciembre), con una o más visitas por día salvo los domingos, y el mes en curso más
# cargado.
#
# Cada reclamo recorre la máquina de estados de verdad (`cambiar_estado`) y después se le
# pone fecha a cada asiento. Las fechas se arman hacia atrás desde la visita, con días
# de por medio entre los pasos que hace una persona: se carga, se revisa al día
# siguiente, los contratistas cotizan unos días después, se aprueba, el contratista
# propone horarios y la escuela elige. Los pasos que dispara el sistema (EN_EVALUACION
# al llegar la primera oferta, PENDIENTE_COORDINACION al aprobar) van en el mismo
# momento que su disparador, como en la app.
#
# Lo que pasa después de la visita depende de la fecha: las futuras quedan en
# VISITA_COORDINADA, las recientes en EN_EJECUCION y las viejas, casi todas, en
# FINALIZADO. Aparte van los que nunca llegaron a una visita (en revisión, esperando
# presupuesto, en evaluación, coordinando, desiertos, rechazados y cancelados).
# ---------------------------------------------------------------------------------------

ART = reloj.ART

# Índices en CONTRATISTAS: 0 electricidad, 1 plomería y gas, 2 obra civil en general.
# Cuando hay más de uno compiten en el mismo reclamo.
CATALOGO = {
    "Electricidad": dict(
        contratistas=[0],
        prioridades=[PrioridadReclamo.ALTA, PrioridadReclamo.ALTA, PrioridadReclamo.MEDIA],
        dias_obra=(1, 3),
        problemas=[
            "Saltan las térmicas de {lugar} varias veces por día.",
            "Tomacorrientes quemados en {lugar}, uno largó chispas.",
            "No funcionan las luminarias de {lugar}.",
            "Cables a la vista en la caja de paso de {lugar}.",
            "El disyuntor del tablero seccional de {lugar} no corta al probarlo.",
            "Olor a quemado en el tablero de {lugar}.",
            "Se quemaron los tubos y el balasto de {lugar}.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Electricista matriculado", "horas", 4, 16, 15000, 19500),
            (TipoItemPresupuesto.MATERIAL, "Cable unipolar 2,5 mm", "metros", 20, 100, 900, 1400),
            (TipoItemPresupuesto.MATERIAL, "Llave termomagnética bipolar 20 A", "unidad", 1, 4, 18000, 26000),
            (TipoItemPresupuesto.MATERIAL, "Interruptor diferencial 40 A", "unidad", 1, 2, 38000, 52000),
            (TipoItemPresupuesto.MATERIAL, "Tomacorriente doble con tierra", "unidad", 2, 10, 4500, 7500),
            (TipoItemPresupuesto.MATERIAL, "Panel LED 60x60", "unidad", 2, 8, 22000, 31000),
        ],
    ),
    "Plomería": dict(
        contratistas=[1, 2],
        prioridades=[PrioridadReclamo.MEDIA, PrioridadReclamo.MEDIA, PrioridadReclamo.ALTA],
        dias_obra=(1, 4),
        problemas=[
            "Pérdida de agua debajo de las bachas de {lugar}.",
            "Inodoros tapados en {lugar}, desbordan al usarlos.",
            "Sin presión de agua en {lugar}.",
            "Gotea la canilla de servicio de {lugar} y no cierra del todo.",
            "Humedad en la pared lindera a {lugar}, se sospecha caño roto.",
            "El tanque de reserva rebalsa: no corta el flotante.",
            "Mochila del inodoro de {lugar} descarga sin parar.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Plomero matriculado", "horas", 3, 14, 14000, 18500),
            (TipoItemPresupuesto.MATERIAL, "Caño termofusión 3/4", "metros", 4, 20, 2800, 4200),
            (TipoItemPresupuesto.MATERIAL, "Llave de paso esférica 3/4", "unidad", 1, 4, 9000, 14000),
            (TipoItemPresupuesto.MATERIAL, "Flotante para tanque", "unidad", 1, 2, 12000, 19000),
            (TipoItemPresupuesto.MATERIAL, "Juego de mecanismo para mochila", "unidad", 1, 4, 15000, 23000),
            (TipoItemPresupuesto.MATERIAL, "Sifón y conexiones para bacha", "unidad", 1, 4, 7000, 11000),
        ],
    ),
    "Gas": dict(
        contratistas=[1],
        prioridades=[PrioridadReclamo.ALTA],
        dias_obra=(1, 5),
        problemas=[
            "Olor a gas en {lugar}, se cerró la llave general.",
            "La estufa de {lugar} se apaga sola: falla la termocupla.",
            "El calefón de {lugar} no enciende.",
            "Pérdida detectada en la prueba de hermeticidad de la cocina.",
            "Rejilla de ventilación obstruida en {lugar}, observada en la inspección.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Gasista matriculado", "horas", 4, 12, 18000, 24000),
            (TipoItemPresupuesto.MATERIAL, "Termocupla universal", "unidad", 1, 4, 8000, 13000),
            (TipoItemPresupuesto.MATERIAL, "Caño epoxi 3/4", "metros", 3, 15, 9000, 13500),
            (TipoItemPresupuesto.MATERIAL, "Llave de paso de gas 1/2", "unidad", 1, 3, 14000, 21000),
            (TipoItemPresupuesto.MATERIAL, "Rejilla de ventilación reglamentaria", "unidad", 1, 4, 6000, 9500),
        ],
    ),
    "Techos": dict(
        contratistas=[2, 1],
        prioridades=[PrioridadReclamo.ALTA, PrioridadReclamo.MEDIA],
        dias_obra=(3, 9),
        problemas=[
            "Goteras en {lugar} cada vez que llueve.",
            "Membrana del techo de {lugar} levantada por el viento.",
            "Canaleta de {lugar} tapada y desbordando sobre el patio.",
            "Mancha de humedad en el cielorraso de {lugar}, se está descascarando.",
            "Chapas sueltas en el techo de {lugar}.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Oficial techista", "horas", 8, 40, 14000, 18000),
            (TipoItemPresupuesto.MATERIAL, "Membrana asfáltica 4 mm con aluminio", "m2", 10, 80, 7500, 11000),
            (TipoItemPresupuesto.MATERIAL, "Pintura impermeabilizante para techos 20 L", "unidad", 1, 4, 85000, 120000),
            (TipoItemPresupuesto.MATERIAL, "Canaleta de chapa galvanizada", "metros", 4, 20, 9000, 14000),
            (TipoItemPresupuesto.MATERIAL, "Chapa acanalada galvanizada", "unidad", 2, 10, 28000, 39000),
        ],
    ),
    "Pintura": dict(
        contratistas=[2],
        prioridades=[PrioridadReclamo.BAJA, PrioridadReclamo.BAJA, PrioridadReclamo.MEDIA],
        dias_obra=(3, 8),
        problemas=[
            "Paredes de {lugar} descascaradas por humedad.",
            "Pintura de las rejas de {lugar} oxidada y saltada.",
            "Pintadas en las paredes de {lugar}.",
            "Hay que repintar {lugar} después del arreglo de la filtración.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Pintor", "horas", 12, 48, 12000, 16000),
            (TipoItemPresupuesto.MATERIAL, "Látex interior lavable 20 L", "unidad", 1, 5, 95000, 135000),
            (TipoItemPresupuesto.MATERIAL, "Fijador sellador 20 L", "unidad", 1, 2, 60000, 85000),
            (TipoItemPresupuesto.MATERIAL, "Esmalte sintético 4 L", "unidad", 1, 4, 38000, 52000),
            (TipoItemPresupuesto.MATERIAL, "Enduido plástico 10 L", "unidad", 1, 3, 30000, 42000),
        ],
    ),
    "Pisos": dict(
        contratistas=[2],
        prioridades=[PrioridadReclamo.MEDIA, PrioridadReclamo.BAJA],
        dias_obra=(2, 7),
        problemas=[
            "Baldosas levantadas en {lugar}, un chico se tropezó.",
            "Piso de {lugar} hundido cerca de la puerta.",
            "Escalón de {lugar} roto, con el borde suelto.",
            "Cerámicos rotos en {lugar}.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Oficial colocador", "horas", 8, 32, 13000, 17000),
            (TipoItemPresupuesto.MATERIAL, "Cerámico antideslizante", "m2", 5, 30, 14000, 21000),
            (TipoItemPresupuesto.MATERIAL, "Pegamento para cerámicos 30 kg", "unidad", 2, 10, 9000, 13000),
            (TipoItemPresupuesto.MATERIAL, "Pastina 5 kg", "unidad", 1, 4, 6000, 9000),
            (TipoItemPresupuesto.MATERIAL, "Cemento portland 50 kg", "unidad", 1, 5, 11000, 14500),
        ],
    ),
    "Aberturas": dict(
        contratistas=[2],
        prioridades=[PrioridadReclamo.MEDIA, PrioridadReclamo.BAJA, PrioridadReclamo.ALTA],
        dias_obra=(1, 4),
        problemas=[
            "La puerta de {lugar} no cierra, se arrastra contra el piso.",
            "Vidrio roto en la ventana de {lugar}.",
            "Cerradura de {lugar} trabada, no se puede abrir con llave.",
            "Barral antipánico de la salida de emergencia de {lugar} no funciona.",
            "Ventana de {lugar} descuadrada, no se puede cerrar.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Oficial carpintero / herrero", "horas", 3, 14, 13500, 17500),
            (TipoItemPresupuesto.MATERIAL, "Vidrio laminado 3+3", "m2", 1, 4, 48000, 65000),
            (TipoItemPresupuesto.MATERIAL, "Cerradura de seguridad doble paleta", "unidad", 1, 3, 26000, 38000),
            (TipoItemPresupuesto.MATERIAL, "Barral antipánico", "unidad", 1, 2, 120000, 165000),
            (TipoItemPresupuesto.MATERIAL, "Bisagras reforzadas (juego)", "unidad", 1, 4, 9000, 14000),
        ],
    ),
    "Albañilería": dict(
        contratistas=[2, 1],
        prioridades=[PrioridadReclamo.MEDIA, PrioridadReclamo.BAJA, PrioridadReclamo.ALTA],
        dias_obra=(3, 10),
        problemas=[
            "Grieta en la pared de {lugar}.",
            "Revoque desprendido en {lugar}, cayeron pedazos.",
            "Muro del cerco perimetral junto a {lugar} inclinado.",
            "Mampostería floja alrededor del marco de {lugar}.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Oficial albañil", "horas", 12, 48, 13000, 17000),
            (TipoItemPresupuesto.MANO_OBRA, "Ayudante", "horas", 12, 48, 9500, 12500),
            (TipoItemPresupuesto.MATERIAL, "Cemento portland 50 kg", "unidad", 3, 15, 11000, 14500),
            (TipoItemPresupuesto.MATERIAL, "Arena (bolsón)", "unidad", 1, 3, 45000, 60000),
            (TipoItemPresupuesto.MATERIAL, "Ladrillo común", "unidad", 100, 600, 220, 330),
        ],
    ),
    "Infraestructura": dict(
        contratistas=[2, 1, 0],
        prioridades=[PrioridadReclamo.MEDIA, PrioridadReclamo.ALTA, PrioridadReclamo.BAJA],
        dias_obra=(2, 8),
        problemas=[
            "Rampa de acceso de {lugar} con la baranda suelta.",
            "Portón de entrada vencido, no cierra con candado.",
            "Bomba de agua de {lugar} hace ruido y corta sola.",
            "Mástil de la bandera de {lugar} oxidado en la base.",
            "Tapa de cámara séptica rota en {lugar}.",
        ],
        items=[
            (TipoItemPresupuesto.MANO_OBRA, "Oficial de mantenimiento", "horas", 6, 30, 13500, 18000),
            (TipoItemPresupuesto.MATERIAL, "Caño estructural 40x40", "metros", 4, 18, 9000, 13000),
            (TipoItemPresupuesto.MATERIAL, "Electrodos y discos de corte (kit)", "unidad", 1, 2, 18000, 26000),
            (TipoItemPresupuesto.MATERIAL, "Tapa de hormigón para cámara", "unidad", 1, 2, 35000, 52000),
            (TipoItemPresupuesto.MATERIAL, "Antióxido y esmalte (kit)", "unidad", 1, 3, 32000, 46000),
        ],
    ),
}

# Más peso a lo que más se rompe en una escuela.
PESOS_CATEGORIA = {
    "Electricidad": 5,
    "Plomería": 5,
    "Gas": 2,
    "Techos": 3,
    "Pintura": 2,
    "Pisos": 2,
    "Aberturas": 3,
    "Albañilería": 2,
    "Infraestructura": 2,
}

LUGARES = [
    "el aula 3", "el aula 5", "el aula 7", "el aula 12", "los baños de nenas",
    "los baños de varones", "el baño de planta alta", "la cocina", "el comedor", "el SUM",
    "la dirección", "la secretaría", "la biblioteca", "el gimnasio", "el patio cubierto",
    "el laboratorio", "la sala de informática", "el pasillo de planta baja", "el jardín",
    "la preceptoría",
]

OBSERVACIONES = [
    None, None, None,
    "Se clausuró el sector hasta que se repare.",
    "Los chicos están dando clase en otra aula.",
    "Ya se había reclamado el año pasado.",
    "Avisar a la portera antes de ir, ella tiene las llaves.",
    "El problema empeora los días de lluvia.",
    "Se puede ir en horario de clase.",
]

MOTIVOS_RECHAZO = [
    "Duplicado de otro reclamo de la misma escuela.",
    "No corresponde a infraestructura escolar: es mobiliario.",
    "Lo resuelve el municipio: es la vereda frente a la escuela.",
    "Falta información para identificar el problema y la escuela no respondió.",
    "El arreglo está cubierto por la garantía de la obra anterior.",
]

MOTIVOS_CANCELACION = [
    "La escuela lo resolvió por sus propios medios.",
    "Se unificó con otro reclamo de la misma escuela.",
    "La cooperadora contrató el arreglo por su cuenta.",
    "El edificio entra en una obra integral de la provincia.",
]

# Horarios en que un contratista va a una escuela (ART).
TURNOS = [(8, 0), (8, 30), (9, 0), (9, 30), (10, 0), (10, 30), (11, 0), (13, 0), (13, 30), (14, 0), (14, 30), (15, 0), (16, 0)]
TURNOS_SABADO = [(8, 0), (9, 0), (10, 0), (11, 0)]

# Sin trabajos: los domingos (ver `_es_laborable`) y estos feriados (mes, día).
FERIADOS = {(12, 8), (12, 25), (1, 1)}


@dataclass
class _Contexto:
    db: object
    rng: random.Random
    contratistas: list
    ahora: datetime
    escuelas: list
    telefonos: dict
    proxima_escuela: int = 0

    def escuela(self):
        institucion = self.escuelas[self.proxima_escuela % len(self.escuelas)]
        self.proxima_escuela += 1
        return institucion


def _es_laborable(dia: date) -> bool:
    return dia.weekday() != 6 and (dia.month, dia.day) not in FERIADOS


def _dias_habiles_antes(dia: date, cantidad: int) -> date:
    """`cantidad` días antes, corrido hacia atrás si cae domingo o feriado."""
    dia -= timedelta(days=cantidad)
    while not _es_laborable(dia):
        dia -= timedelta(days=1)
    return dia


def _dias_habiles_despues(dia: date, cantidad: int) -> date:
    dia += timedelta(days=cantidad)
    while not _es_laborable(dia):
        dia += timedelta(days=1)
    return dia


def _a_las(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ART)


def _momento(rng, dia: date, desde: int, hasta: int) -> datetime:
    """Una hora cualquiera de `dia` entre `desde` y `hasta` (exclusive)."""
    return _a_las(dia, rng.randint(desde, hasta - 1), rng.randrange(0, 60, 5))


def _antes_de(rng, momento: datetime, tope: datetime) -> datetime:
    """`momento`, o un rato antes de `tope` si se pasaba: nada puede pasar en el futuro."""
    if momento < tope:
        return momento
    return tope - timedelta(minutes=rng.randint(20, 240))


def _paso(ctx, reclamo, estado, fecha, motivo=None, origen=OrigenCambioEstado.MANUAL):
    evento = estados_reclamo.cambiar_estado(ctx.db, reclamo, estado, motivo=motivo, origen=origen)
    evento.fecha = fecha
    return evento


def _nuevo_reclamo(ctx, categoria, creado):
    rng = ctx.rng
    datos = CATALOGO[categoria]
    institucion = ctx.escuela()
    alta_whatsapp = rng.random() < 0.75
    reclamo = Reclamo(
        nombre_escuela=" ".join(institucion.nombre.split()),
        ubicacion=" ".join((institucion.domicilio or "").split()),
        prioridad=rng.choice(datos["prioridades"]),
        categoria=categoria,
        descripcion=rng.choice(datos["problemas"]).format(lugar=rng.choice(LUGARES)),
        observaciones=rng.choice(OBSERVACIONES),
        # El número simulado ("sim...") nunca sale a Meta, aunque haya token cargado.
        telefono_creador=ctx.telefonos.setdefault(
            institucion.id, f"sim549115{rng.randint(1000000, 9999999)}"
        ),
        alta_whatsapp=alta_whatsapp,
        estado=estados_reclamo.ESTADO_INICIAL,
        fecha_creacion=creado,
    )
    ctx.db.add(reclamo)
    inicial = estados_reclamo.registrar_estado_inicial(ctx.db, reclamo)
    inicial.fecha = creado
    ctx.db.flush()
    return reclamo


def _items(rng, categoria):
    """La mano de obra principal siempre, más algunos materiales."""
    plantillas = CATALOGO[categoria]["items"]
    elegidas = [plantillas[0]] + rng.sample(plantillas[1:], rng.randint(1, min(3, len(plantillas) - 1)))
    items = []
    for tipo, descripcion, unidad, cant_min, cant_max, costo_min, costo_max in elegidas:
        items.append(
            ItemPresupuesto(
                tipo=tipo,
                descripcion=descripcion,
                unidad=unidad,
                cantidad=rng.randint(cant_min, cant_max),
                costo_unitario=rng.randrange(costo_min, costo_max + 1, 100),
            )
        )
    return items


def _monto(presupuesto):
    return sum(item.cantidad * item.costo_unitario for item in presupuesto.items)


def _pedir_presupuestos(ctx, reclamo, revisado):
    """Se le pide cotización a todos los contratistas del rubro, un rato después de
    validar el reclamo. Devuelve los contratistas convocados."""
    convocados = [ctx.contratistas[i] for i in CATALOGO[reclamo.categoria]["contratistas"]]
    for contratista in convocados:
        pedido = revisado + timedelta(minutes=ctx.rng.randint(10, 180))
        ctx.db.add(
            SolicitudPresupuesto(
                reclamo_id=reclamo.id,
                contratista_id=contratista.id,
                fecha_solicitud=pedido,
                fecha_ultimo_aviso=pedido,
            )
        )
    return convocados


def _recibir_ofertas(ctx, reclamo, convocados, fechas):
    """Una oferta por cada fecha, de contratistas distintos de los convocados. El
    reclamo pasa a EN_EVALUACION con la primera, como lo hace el sistema."""
    rng = ctx.rng
    oferentes = rng.sample(convocados, len(fechas))
    presupuestos = []
    for contratista, fecha in zip(oferentes, sorted(fechas)):
        presupuesto = Presupuesto(
            reclamo=reclamo,
            contratista=contratista,
            detalle_tarea=f"Reparación: {reclamo.descripcion[0].lower()}{reclamo.descripcion[1:]}",
            observaciones=rng.choice(
                [None, "Incluye materiales y retiro de escombros.", "Validez de la oferta: 15 días.",
                 "Se puede empezar dentro de la semana de aprobado."]
            ),
            items=_items(rng, reclamo.categoria),
            estado=estados_presupuesto.ESTADO_INICIAL,
            fecha=fecha,
        )
        ctx.db.add(presupuesto)
        estados_presupuesto.registrar_estado_inicial(ctx.db, presupuesto).fecha = fecha
        presupuestos.append(presupuesto)

    evento = estados_reclamo.sincronizar_por_presupuestos(ctx.db, reclamo)
    if evento is not None:
        evento.fecha = min(fechas)
    return presupuestos


def _hasta_aprobacion(ctx, categoria, aprobado):
    """Reclamo que llega a PENDIENTE_COORDINACION en `aprobado`, con las etapas
    anteriores repartidas en los días previos. Devuelve (reclamo, visita)."""
    rng = ctx.rng
    db = ctx.db

    dia_oferta = _dias_habiles_antes(aprobado.date(), rng.randint(1, 4))
    primera_oferta = _momento(rng, dia_oferta, 8, 20)
    dia_revision = _dias_habiles_antes(dia_oferta, rng.randint(1, 3))
    revisado = _momento(rng, dia_revision, 9, 17)
    creado = _momento(rng, _dias_habiles_antes(dia_revision, rng.randint(0, 2)), 7, 21)
    if creado > revisado - timedelta(hours=2):
        creado = revisado - timedelta(hours=rng.randint(2, 6))

    reclamo = _nuevo_reclamo(ctx, categoria, creado)
    _paso(ctx, reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, revisado)
    convocados = _pedir_presupuestos(ctx, reclamo, revisado)

    cantidad = rng.randint(1, len(convocados))
    margen = (aprobado - timedelta(hours=2) - primera_oferta).total_seconds()
    fechas = [primera_oferta] + [
        primera_oferta + timedelta(seconds=rng.uniform(0, max(margen, 0))) for _ in range(cantidad - 1)
    ]
    presupuestos = _recibir_ofertas(ctx, reclamo, convocados, fechas)

    # Casi siempre gana la más barata.
    if rng.random() < 0.75:
        ganador = min(presupuestos, key=_monto)
    else:
        ganador = rng.choice(presupuestos)
    perdedores = [p for p in presupuestos if p is not ganador]

    if perdedores and rng.random() < 0.2:
        rechazado = perdedores.pop()
        estados_presupuesto.cambiar_estado(
            db, rechazado, EstadoPresupuesto.RECHAZADO,
            motivo="El monto supera ampliamente la referencia de costos.",
        ).fecha = aprobado - timedelta(minutes=rng.randint(30, 90))

    estados_presupuesto.cambiar_estado(db, ganador, EstadoPresupuesto.APROBADO).fecha = aprobado
    for perdedor in perdedores:
        estados_presupuesto.cambiar_estado(
            db, perdedor, EstadoPresupuesto.NO_SELECCIONADO,
            motivo=f"Se aprobó el presupuesto #{ganador.id}",
            origen=OrigenCambioEstado.AUTOMATICO,
        ).fecha = aprobado
    estados_reclamo.sincronizar_por_presupuestos(db, reclamo).fecha = aprobado

    # El bot le pide disponibilidad al contratista en el momento de la aprobación.
    pedido = aprobado + timedelta(minutes=1)
    _paso(
        ctx, reclamo, EstadoReclamo.PENDIENTE_COORDINACION, pedido,
        motivo="Se solicitó disponibilidad al contratista para coordinar la visita",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    visita = Visita(
        reclamo_id=reclamo.id,
        contratista_id=ganador.contratista.id,
        estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
        fecha_creacion=pedido,
    )
    db.add(visita)
    db.flush()
    return reclamo, visita


def _opciones_alrededor(rng, fecha, cantidad):
    """Otros horarios que el contratista pudo haber ofrecido, en días cercanos."""
    opciones = []
    dia = fecha.date()
    for _ in range(cantidad):
        dia = _dias_habiles_despues(dia, rng.randint(1, 2))
        hora, minuto = rng.choice(TURNOS)
        opciones.append(_a_las(dia, hora, minuto))
    return opciones


def _seguimiento(ctx, reclamo):
    """La fila que deja `reiniciar_reloj_seguimiento` al pasar a EN_EJECUCION."""
    ctx.db.flush()
    return ctx.db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()


def _reclamo_con_visita(ctx, categoria, visita_en):
    rng = ctx.rng
    ahora = ctx.ahora

    # La escuela elige el horario unos días antes de la visita, siempre en el pasado.
    dia_eleccion = _dias_habiles_antes(visita_en.date(), rng.randint(2, 6))
    if dia_eleccion >= ahora.date():
        dia_eleccion = _dias_habiles_antes(ahora.date(), rng.randint(0, 5))
    elegido = _antes_de(rng, _momento(rng, dia_eleccion, 8, 21), ahora)
    aprobado = _momento(rng, _dias_habiles_antes(elegido.date(), rng.randint(1, 3)), 9, 18)

    reclamo, visita = _hasta_aprobacion(ctx, categoria, aprobado)

    opciones = [visita_en] + _opciones_alrededor(rng, visita_en, rng.randint(1, 2))
    rng.shuffle(opciones)
    horario = reloj.formatear_art(visita_en)
    visita.disponibilidades = "\n".join(reloj.formatear_art(op) for op in opciones)
    visita.horario_confirmado = horario
    visita.fecha_visita = visita_en
    visita.estado = EstadoVisita.CONFIRMADA
    _paso(
        ctx, reclamo, EstadoReclamo.VISITA_COORDINADA, elegido,
        motivo=f"Visita de trabajo coordinada para: {horario}",
        origen=OrigenCambioEstado.AUTOMATICO,
    )

    # Los recordatorios que el scheduler ya habría mandado.
    dia_antes = visita_en - timedelta(hours=24)
    if elegido < dia_antes <= ahora:
        visita.recordatorio_dia_antes_enviado = dia_antes
    mismo_dia = visita_en - timedelta(hours=rng.randint(2, 10))
    if elegido < mismo_dia <= ahora:
        visita.recordatorio_mismo_dia_enviado = mismo_dia

    if visita_en > ahora - timedelta(minutes=20):
        return reclamo

    # Pasó la hora pactada: se le preguntó al contratista y respondió que empezó.
    visita.pregunta_inicio_enviada = visita_en
    inicio = visita_en + timedelta(minutes=rng.randint(15, 150))
    if inicio >= ahora:
        inicio = visita_en + (ahora - visita_en) / 2
    _paso(
        ctx, reclamo, EstadoReclamo.EN_EJECUCION, inicio,
        motivo="El contratista avisó por WhatsApp que inició la obra",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    seguimiento = _seguimiento(ctx, reclamo)
    seguimiento.creado_en = inicio

    # Unos pocos se quedan sin respuesta del contratista a los avisos de avance.
    if ahora - inicio > timedelta(days=7) and rng.random() < 0.06:
        intentos = 5
        intervencion = inicio + timedelta(days=intentos, hours=rng.randint(1, 12))
        _paso(
            ctx, reclamo, EstadoReclamo.PENDIENTE_INTERVENCION, intervencion,
            motivo=f"El contratista no respondió {intentos} recordatorios de avance.",
            origen=OrigenCambioEstado.AUTOMATICO,
        )
        seguimiento.cantidad_envios = intentos
        seguimiento.ultimo_envio = intervencion - timedelta(hours=24)
        return reclamo

    dia_fin = _dias_habiles_despues(inicio.date(), rng.randint(*CATALOGO[categoria]["dias_obra"]))
    finalizado = _momento(rng, dia_fin, 9, 20)
    if finalizado < ahora - timedelta(hours=1):
        if rng.random() < 0.7:
            motivo = "La escuela confirmó por WhatsApp que el problema se resolvió"
            origen = OrigenCambioEstado.AUTOMATICO
        else:
            motivo = "Se verificó el trabajo terminado con la dirección de la escuela."
            origen = OrigenCambioEstado.MANUAL
        _paso(ctx, reclamo, EstadoReclamo.FINALIZADO, finalizado, motivo=motivo, origen=origen)
        seguimiento.ultimo_envio = finalizado - timedelta(hours=rng.randint(2, 20))
        seguimiento.consulto_escuela = True
    else:
        # Sigue en obra: la última pregunta de avance fue hace menos de un día.
        seguimiento.ultimo_envio = max(inicio, ahora - timedelta(hours=rng.randint(1, 20)))
        seguimiento.cantidad_envios = 0
    return reclamo


def _categoria(rng):
    categorias = list(PESOS_CATEGORIA)
    return rng.choices(categorias, weights=[PESOS_CATEGORIA[c] for c in categorias])[0]


def _hace(ctx, dias_min, dias_max, desde=8, hasta=20):
    """Un momento hábil entre `dias_min` y `dias_max` días atrás, nunca en el futuro."""
    dia = _dias_habiles_antes(ctx.ahora.date(), ctx.rng.randint(dias_min, dias_max))
    return _antes_de(ctx.rng, _momento(ctx.rng, dia, desde, hasta), ctx.ahora)


def _reclamos_sin_visita(ctx):
    """Los que todavía no llegaron a una visita (o nunca van a llegar)."""
    rng = ctx.rng
    ahora = ctx.ahora

    # Recién cargados, esperando que alguien los revise.
    for _ in range(8):
        _nuevo_reclamo(ctx, _categoria(rng), _hace(ctx, 0, 3, 7, 22))

    # Validados, con el pedido de cotización hecho y sin ofertas todavía.
    for _ in range(7):
        creado = _hace(ctx, 4, 12)
        reclamo = _nuevo_reclamo(ctx, _categoria(rng), creado)
        revisado = _antes_de(rng, _momento(rng, _dias_habiles_despues(creado.date(), rng.randint(1, 2)), 9, 17), ahora)
        _paso(ctx, reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, revisado)
        _pedir_presupuestos(ctx, reclamo, revisado)

    # Con ofertas cargadas, esperando la decisión.
    for i in range(10):
        creado = _hace(ctx, 6, 16)
        reclamo = _nuevo_reclamo(ctx, _categoria(rng), creado)
        revisado = _momento(rng, _dias_habiles_despues(creado.date(), rng.randint(1, 2)), 9, 17)
        _paso(ctx, reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, revisado)
        convocados = _pedir_presupuestos(ctx, reclamo, revisado)
        desde = revisado + timedelta(days=1)
        fechas = [
            _antes_de(rng, desde + timedelta(seconds=rng.uniform(0, (ahora - desde).total_seconds())), ahora)
            for _ in range(rng.randint(1, len(convocados)))
        ]
        presupuestos = _recibir_ofertas(ctx, reclamo, convocados, fechas)
        if i % 4 == 0:
            ultimo = max(presupuestos, key=lambda p: p.fecha)
            estados_presupuesto.cambiar_estado(
                ctx.db, ultimo, EstadoPresupuesto.AJUSTES_SOLICITADOS,
                motivo="Detallar por separado materiales y mano de obra.",
            ).fecha = _antes_de(rng, ultimo.fecha + timedelta(hours=rng.randint(4, 30)), ahora)

    # Aprobados, esperando que el contratista mande sus horarios.
    for _ in range(4):
        _hasta_aprobacion(ctx, _categoria(rng), _hace(ctx, 0, 2, 9, 18))

    # El contratista ya propuso horarios y la escuela todavía no eligió.
    for _ in range(4):
        aprobado = _hace(ctx, 1, 4, 9, 18)
        _, visita = _hasta_aprobacion(ctx, _categoria(rng), aprobado)
        primera = _a_las(_dias_habiles_despues(ahora.date(), rng.randint(2, 5)), *rng.choice(TURNOS))
        opciones = [primera] + _opciones_alrededor(rng, primera, rng.randint(1, 2))
        visita.disponibilidades = "\n".join(reloj.formatear_art(op) for op in opciones)
        visita.estado = EstadoVisita.ESPERANDO_ELECCION

    # Llamados desiertos: nadie cotizó en los 15 días de plazo.
    for _ in range(3):
        creado = _hace(ctx, 22, 50)
        reclamo = _nuevo_reclamo(ctx, _categoria(rng), creado)
        revisado = _momento(rng, _dias_habiles_despues(creado.date(), rng.randint(1, 2)), 9, 17)
        _paso(ctx, reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, revisado)
        _pedir_presupuestos(ctx, reclamo, revisado)
        _paso(
            ctx, reclamo, EstadoReclamo.DESIERTO, revisado + timedelta(days=15),
            motivo="Ningún contratista cotizó dentro del plazo de 15 días.",
            origen=OrigenCambioEstado.AUTOMATICO,
        )

    # Rechazados en la revisión.
    for _ in range(6):
        creado = _hace(ctx, 2, 55)
        reclamo = _nuevo_reclamo(ctx, _categoria(rng), creado)
        rechazado = _antes_de(rng, _momento(rng, _dias_habiles_despues(creado.date(), rng.randint(1, 2)), 9, 17), ahora)
        _paso(ctx, reclamo, EstadoReclamo.RECHAZADO, rechazado, motivo=rng.choice(MOTIVOS_RECHAZO))

    # Cancelados en distintas etapas.
    for _ in range(2):
        creado = _hace(ctx, 10, 45)
        reclamo = _nuevo_reclamo(ctx, _categoria(rng), creado)
        revisado = _momento(rng, _dias_habiles_despues(creado.date(), 1), 9, 17)
        _paso(ctx, reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, revisado)
        _pedir_presupuestos(ctx, reclamo, revisado)
        cancelado = _momento(rng, _dias_habiles_despues(revisado.date(), rng.randint(2, 6)), 9, 17)
        _paso(ctx, reclamo, EstadoReclamo.CANCELADO, cancelado, motivo=rng.choice(MOTIVOS_CANCELACION))
    for _ in range(2):
        aprobado = _hace(ctx, 12, 40, 9, 18)
        reclamo, visita = _hasta_aprobacion(ctx, _categoria(rng), aprobado)
        cancelado = _momento(rng, _dias_habiles_despues(aprobado.date(), rng.randint(1, 3)), 9, 17)
        _paso(ctx, reclamo, EstadoReclamo.CANCELADO, cancelado, motivo=rng.choice(MOTIVOS_CANCELACION))


def _dias_de_visita(ahora):
    """Del primer día del mes pasado al último del mes que viene."""
    mes_pasado = (ahora.replace(day=1) - timedelta(days=1)).replace(day=1)
    siguiente = (ahora.replace(day=28) + timedelta(days=4)).replace(day=1)
    fin = (siguiente.replace(day=28) + timedelta(days=4)).replace(day=1)
    dia = mes_pasado.date()
    while dia < fin.date():
        if _es_laborable(dia):
            yield dia
        dia += timedelta(days=1)


def _seed_reclamos_historicos(db, contratistas):
    ahora = reloj.ahora_art()
    rng = random.Random(2026)
    escuelas = db.query(Institucion).order_by(Institucion.id).all()
    rng.shuffle(escuelas)
    ctx = _Contexto(db=db, rng=rng, contratistas=contratistas, ahora=ahora, escuelas=escuelas, telefonos={})

    for dia in _dias_de_visita(ahora):
        if dia.weekday() == 5:
            cantidad, turnos = 1, TURNOS_SABADO
        elif dia.month == ahora.month:
            cantidad, turnos = rng.choice([2, 3, 3, 4]), TURNOS
        else:
            cantidad, turnos = rng.choice([1, 1, 2]), TURNOS
        for hora, minuto in sorted(rng.sample(turnos, cantidad)):
            _reclamo_con_visita(ctx, _categoria(rng), _a_las(dia, hora, minuto))

    _reclamos_sin_visita(ctx)
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
    _seed_reclamos_historicos(db, contratistas)

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


def reaplicar_permisos_solo_lectura(db):
    """Re-otorga SELECT al rol de solo lectura (Adminer) sobre las tablas actuales.

    `--reset` recrea las tablas, así que los GRANT dados a mano quedan sobre tablas que
    ya no existen y el rol pierde acceso. Esto lo vuelve a dejar consultando todo, sin
    tener que acordarse de correr los GRANT después de cada reset.

    No crea el rol ni le toca la contraseña: si no existe (p. ej. en dev), no hace nada.
    El nombre del rol se puede cambiar con DB_READONLY_ROLE (default: lector).
    """
    import os

    from sqlalchemy import text

    rol = (os.getenv("DB_READONLY_ROLE") or "lector").strip()
    if not rol.isidentifier():
        logger.warning("DB_READONLY_ROLE inválido (%r); se omite reaplicar permisos", rol)
        return

    existe = db.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :rol"), {"rol": rol}
    ).scalar()
    if not existe:
        logger.info("Rol de solo lectura %r no existe; no se reaplican permisos", rol)
        return

    # El rol va interpolado (no admite bind param en GRANT), por eso se validó isidentifier.
    db.execute(text(f'GRANT USAGE ON SCHEMA public TO "{rol}"'))
    db.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{rol}"'))
    db.execute(
        text(
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "{rol}"'
        )
    )
    db.commit()
    logger.info("Permisos de solo lectura reaplicados al rol %r.", rol)


def main():
    # Los servicios que usa el seed avisan por WhatsApp (al aprobar un presupuesto se le
    # escribe al contratista). Sin token, el cliente simula el envío en vez de escribirle
    # a los números del seed.
    whatsapp_client.WHATSAPP_TOKEN = ""
    reiniciar = "--reset" in sys.argv
    if reiniciar:
        logger.info("Recreando el schema desde los modelos...")
        reset_schema()
    else:
        Base.metadata.create_all(bind=engine)
        asegurar_columna_tipo_item()
        asegurar_columna_detalle_tarea()
        asegurar_columna_autor_foto()
        asegurar_columnas_seguimiento()
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

        # Tras recrear/crear tablas, re-otorgar SELECT al rol de solo lectura (Adminer).
        # Se hace siempre, antes del posible return de abajo, para que un --reset no deje
        # al rol sin acceso a las tablas nuevas.
        reaplicar_permisos_solo_lectura(db)

        refs_csv = sincronizar_desde_csv(db)
        if refs_csv.creadas or refs_csv.actualizadas:
            db.commit()
            logger.info(
                "Referencias de costo desde CSV: %d nuevas, %d actualizadas.",
                refs_csv.creadas,
                refs_csv.actualizadas,
            )

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
