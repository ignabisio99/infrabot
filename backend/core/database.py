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
