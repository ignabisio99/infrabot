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


def asegurar_columna_pregunta_inicio_enviada(bind=engine):
    """Agrega `visita.pregunta_inicio_enviada` si la tabla ya existía sin esa columna."""
    inspector = inspect(bind)
    if "visita" not in inspector.get_table_names():
        return
    columnas = {columna["name"] for columna in inspector.get_columns("visita")}
    if "pregunta_inicio_enviada" in columnas:
        return
    with bind.begin() as conn:
        conn.execute(
            text("ALTER TABLE visita ADD COLUMN pregunta_inicio_enviada TIMESTAMPTZ")
        )


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
