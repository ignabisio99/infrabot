"""Fixtures compartidas por los tests del backend.

Las agregaciones del dashboard usan `date_trunc` y `timezone(...)` de Postgres, así que
los tests corren contra Postgres de verdad y no contra SQLite. Para no mezclarse con los
datos de desarrollo usan una base aparte (`<base>_test`) en la misma instancia, y cada
test se envuelve en una transacción que se revierte al terminar.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import models  # noqa: F401 - registra todos los modelos antes del create_all
from core.database import Base, get_db
from core.dependencies import get_current_admin
from main import app
from models.contratista import Contratista
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import HistorialEstadoReclamo
from models.presupuesto import EstadoPresupuesto, ItemPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, PrioridadReclamo, Reclamo
from models.usuario import TipoUsuario, Usuario
from models.visita import EstadoVisita, Visita

UTC = timezone.utc


@pytest.fixture(scope="session")
def engine():
    url = make_url(os.environ["DATABASE_URL"])
    url_test = url.set(database=f"{url.database}_test")

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        existe = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :nombre"),
            {"nombre": url_test.database},
        ).scalar()
        if not existe:
            conn.execute(text(f'CREATE DATABASE "{url_test.database}"'))
    admin.dispose()

    engine_test = create_engine(url_test)
    Base.metadata.create_all(bind=engine_test)
    yield engine_test
    engine_test.dispose()


@pytest.fixture
def db(engine):
    conexion = engine.connect()
    transaccion = conexion.begin()
    # create_savepoint: si el código bajo test hace commit, se cierra un savepoint y no la
    # transacción externa, así el rollback del final sigue limpiando todo.
    session = Session(bind=conexion, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def client(db):
    """TestClient con la sesión del test y la autenticación de admin ya resueltas.

    Se instancia sin `with` a propósito: así no corre el lifespan, que arrancaría el loop
    de recordatorios y haría un create_all sobre la base de desarrollo.
    """
    admin = Usuario(
        nombre="Admin",
        email="admin@test.local",
        password_hash="x",
        tipo=TipoUsuario.ADMINISTRADOR,
    )

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_admin] = lambda: admin

    yield TestClient(app)

    app.dependency_overrides.clear()


# --- Factories -------------------------------------------------------------------------
# Sólo piden lo que el test necesita mirar; el resto son valores de relleno.


@pytest.fixture
def crear_reclamo(db):
    def _crear(estado=EstadoReclamo.PENDIENTE_REVISION, fecha_creacion=None, **campos):
        reclamo = Reclamo(
            nombre_escuela=campos.pop("nombre_escuela", "Escuela de prueba"),
            ubicacion="Ubicación",
            prioridad=campos.pop("prioridad", PrioridadReclamo.MEDIA),
            estado=estado,
            categoria="Categoría",
            descripcion="Descripción",
            fecha_creacion=fecha_creacion or datetime.now(UTC),
            **campos,
        )
        db.add(reclamo)
        db.flush()
        return reclamo

    return _crear


@pytest.fixture
def crear_historial(db):
    def _crear(reclamo, estado_nuevo, fecha):
        asiento = HistorialEstadoReclamo(
            reclamo_id=reclamo.id,
            estado_nuevo=estado_nuevo,
            fecha=fecha,
        )
        db.add(asiento)
        db.flush()
        return asiento

    return _crear


@pytest.fixture
def crear_contratista(db):
    def _crear(nombre_empresa="Constructora de prueba"):
        contratista = Contratista(
            nombre_empresa=nombre_empresa,
            telefono="1122334455",
            direccion="Dirección",
            especialidad="Albañilería",
        )
        db.add(contratista)
        db.flush()
        return contratista

    return _crear


@pytest.fixture
def crear_presupuesto_aprobado(db, crear_contratista):
    """Presupuesto APROBADO con sus ítems y el asiento de aprobación en `fecha_aprobacion`."""

    def _crear(reclamo, items, fecha_aprobacion, contratista=None):
        contratista = contratista or crear_contratista()
        presupuesto = Presupuesto(
            reclamo_id=reclamo.id,
            contratista_id=contratista.id,
            estado=EstadoPresupuesto.APROBADO,
        )
        db.add(presupuesto)
        db.flush()

        for cantidad, costo_unitario in items:
            db.add(
                ItemPresupuesto(
                    presupuesto_id=presupuesto.id,
                    descripcion="Ítem",
                    cantidad=Decimal(str(cantidad)),
                    costo_unitario=Decimal(str(costo_unitario)),
                )
            )

        db.add(
            HistorialEstadoPresupuesto(
                presupuesto_id=presupuesto.id,
                estado_nuevo=EstadoPresupuesto.APROBADO,
                fecha=fecha_aprobacion,
            )
        )
        db.flush()
        return presupuesto

    return _crear


@pytest.fixture
def crear_visita(db, crear_contratista):
    def _crear(reclamo, fecha_visita, estado=EstadoVisita.CONFIRMADA, contratista=None):
        contratista = contratista or crear_contratista()
        visita = Visita(
            reclamo_id=reclamo.id,
            contratista_id=contratista.id,
            estado=estado,
            fecha_visita=fecha_visita,
        )
        db.add(visita)
        db.flush()
        return visita

    return _crear
