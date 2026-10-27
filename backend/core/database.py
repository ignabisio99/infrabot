import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def asegurar_columna_tipo_item(bind=engine):
    """Agrega `item_presupuesto.tipo` si la tabla ya existía sin esa columna.

    `create_all` no altera tablas viejas. Sin esto, hay que recrear el schema
    (`seed.py --reset`) para poder guardar materiales y mano de obra.
    """
    inspector = inspect(bind)
    if "item_presupuesto" not in inspector.get_table_names():
        return
    columnas = {columna["name"] for columna in inspector.get_columns("item_presupuesto")}
    if "tipo" in columnas:
        return
    with bind.begin() as conn:
        conn.execute(
            text(
                """
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'tipo_item_presupuesto'
                    ) THEN
                        CREATE TYPE tipo_item_presupuesto AS ENUM ('MATERIAL', 'MANO_OBRA');
                    END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE item_presupuesto
                ADD COLUMN tipo tipo_item_presupuesto NOT NULL DEFAULT 'MATERIAL';
                """
            )
        )


def asegurar_columna_detalle_tarea(bind=engine):
    """Agrega `presupuesto.detalle_tarea` si la tabla ya existía sin esa columna."""
    inspector = inspect(bind)
    if "presupuesto" not in inspector.get_table_names():
        return
    columnas = {columna["name"] for columna in inspector.get_columns("presupuesto")}
    if "detalle_tarea" in columnas:
        return
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE presupuesto ADD COLUMN detalle_tarea TEXT"))


def asegurar_columna_ultimo_aviso(bind=engine):
    """Agrega `solicitud_presupuesto.fecha_ultimo_aviso` si la tabla ya existía sin esa
    columna. Las solicitudes viejas toman la fecha del pedido: hasta ahora el reenvío no
    quedaba registrado."""
    inspector = inspect(bind)
    if "solicitud_presupuesto" not in inspector.get_table_names():
        return
    columnas = {columna["name"] for columna in inspector.get_columns("solicitud_presupuesto")}
    if "fecha_ultimo_aviso" in columnas:
        return
    with bind.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE solicitud_presupuesto "
                "ADD COLUMN fecha_ultimo_aviso TIMESTAMP WITH TIME ZONE"
            )
        )
        conn.execute(text("UPDATE solicitud_presupuesto SET fecha_ultimo_aviso = fecha_solicitud"))


def asegurar_columna_autor_foto(bind=engine):
    """Agrega `foto_reclamo.usuario_id` si la tabla ya existía sin esa columna."""
    inspector = inspect(bind)
    if "foto_reclamo" not in inspector.get_table_names():
        return
    columnas = {columna["name"] for columna in inspector.get_columns("foto_reclamo")}
    if "usuario_id" in columnas:
        return
    with bind.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE foto_reclamo ADD COLUMN usuario_id INTEGER "
                "REFERENCES usuario(id) ON DELETE SET NULL"
            )
        )


def asegurar_columnas_seguimiento(bind=engine):
    """Agrega las columnas del seguimiento de obra si las tablas ya existían sin ellas."""
    faltantes = {
        "visita": {
            "pregunta_inicio_enviada": "TIMESTAMP WITH TIME ZONE",
            "disponibilidad_pausada": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "recordatorio_contratista": {
            "proxima_pregunta": "TIMESTAMP WITH TIME ZONE",
            "consulto_escuela": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
    }
    inspector = inspect(bind)
    tablas = inspector.get_table_names()
    with bind.begin() as conn:
        for tabla, columnas in faltantes.items():
            if tabla not in tablas:
                continue
            existentes = {columna["name"] for columna in inspector.get_columns(tabla)}
            for columna, tipo in columnas.items():
                if columna not in existentes:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))


def asegurar_columna_pregunta_inicio_enviada(bind=engine):
    """Compat: la columna quedó en `asegurar_columnas_seguimiento`."""
    asegurar_columnas_seguimiento(bind=bind)


def asegurar_valores_estado_reclamo(bind=engine):
    """Agrega valores nuevos al enum `estado_reclamo` si la base se creó antes.

    `create_all` no altera un tipo enum que ya existe.
    """
    from models.reclamo import EstadoReclamo

    with bind.begin() as conn:
        for valor in EstadoReclamo:
            conn.execute(
                text(f"ALTER TYPE estado_reclamo ADD VALUE IF NOT EXISTS '{valor.value}'")
            )


def asegurar_valores_estado_presupuesto(bind=engine):
    """Agrega valores nuevos al enum `estado_presupuesto` si la base se creó antes."""
    from models.presupuesto import EstadoPresupuesto

    with bind.begin() as conn:
        for valor in EstadoPresupuesto:
            conn.execute(
                text(f"ALTER TYPE estado_presupuesto ADD VALUE IF NOT EXISTS '{valor.value}'")
            )


def asegurar_tipo_usuario_inspector(bind=engine):
    """Agrega INSPECTOR al enum `tipo_usuario` si la base se creó antes de ese valor.

    `create_all` no toca un tipo enum que ya existe. Tiene que correr después de
    `create_all`, que es quien crea el tipo en una base nueva.
    """
    with bind.begin() as conn:
        conn.execute(text("ALTER TYPE tipo_usuario ADD VALUE IF NOT EXISTS 'INSPECTOR'"))


def asegurar_valor_analisis_agente(bind=engine):
    """Agrega valores nuevos al enum `tipo_recomendacion_ia` si la base es anterior.

    `create_all` no altera un enum ya existente. Sin STT, registrar una transcripción
    de audio falla con 'invalid input value for enum'.
    """
    from models.recomendacion_ia import TipoRecomendacionIA

    with bind.begin() as conn:
        for valor in TipoRecomendacionIA:
            # El nombre del valor del enum es literal; no se puede bindear.
            conn.execute(
                text(
                    f"ALTER TYPE tipo_recomendacion_ia ADD VALUE IF NOT EXISTS '{valor.value}'"
                )
            )


def asegurar_emails_unicos(bind=engine):
    """Pasa los emails a minúsculas y crea un índice único sobre lower(email).

    La app ya normaliza los emails al registrar y al entrar con Google; el índice es la
    última barrera para que no queden dos cuentas con el mismo email ("Juan@..." y
    "juan@..."). Si la base ya tuviera duplicados así, no toca nada y lo deja en el log:
    hay que resolverlos a mano (decidir con qué cuenta se queda la persona).
    """
    import logging

    logger = logging.getLogger(__name__)
    with bind.begin() as conn:
        duplicados = conn.execute(
            text(
                "SELECT lower(email) FROM usuario GROUP BY lower(email) HAVING count(*) > 1"
            )
        ).scalars().all()
        if duplicados:
            logger.error(
                "Hay cuentas con el mismo email en distinta mayúscula: %s. No se crea el "
                "índice único hasta resolverlas.",
                ", ".join(duplicados),
            )
            return
        conn.execute(text("UPDATE usuario SET email = lower(trim(email)) WHERE email <> lower(trim(email))"))
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_email_lower ON usuario (lower(email))")
        )


def cancelar_visitas_de_reclamos_cancelados(bind=engine):
    """Da de baja las visitas que quedaron vivas en reclamos ya cancelados.

    Antes, cancelar el reclamo no tocaba la visita y el scheduler seguía mandando los
    recordatorios. Ahora lo hace `estados_reclamo.cambiar_estado`; esto arregla las que
    quedaron de antes.
    """
    with bind.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE visita SET estado = 'CANCELADA'
                FROM reclamo
                WHERE reclamo.id = visita.reclamo_id
                  AND reclamo.estado = 'CANCELADO'
                  AND visita.estado <> 'CANCELADA'
                """
            )
        )


def asegurar_baja_de_contratistas(bind=engine):
    """Agrega `contratista.fecha_baja` y pasa a RESTRICT las FKs que cuelgan del contratista.

    Con CASCADE, borrar un contratista se llevaba sus presupuestos, visitas y
    convocatorias, y con ellos el expediente de reclamos ya cerrados.
    """
    inspector = inspect(bind)
    tablas = inspector.get_table_names()
    if "contratista" not in tablas:
        return
    with bind.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE contratista "
                "ADD COLUMN IF NOT EXISTS fecha_baja TIMESTAMP WITH TIME ZONE"
            )
        )
        for tabla in ("presupuesto", "visita", "solicitud_presupuesto"):
            if tabla not in tablas:
                continue
            for fk in inspector.get_foreign_keys(tabla):
                if fk["referred_table"] != "contratista":
                    continue
                if fk["options"].get("ondelete") == "RESTRICT":
                    continue
                columnas = ", ".join(fk["constrained_columns"])
                conn.execute(text(f'ALTER TABLE {tabla} DROP CONSTRAINT "{fk["name"]}"'))
                conn.execute(
                    text(
                        f'ALTER TABLE {tabla} ADD CONSTRAINT "{fk["name"]}" '
                        f"FOREIGN KEY ({columnas}) REFERENCES contratista(id) ON DELETE RESTRICT"
                    )
                )
