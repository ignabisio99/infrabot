"""El listado dice cuándo cambió de estado cada reclamo por última vez, con el mismo
criterio que los estancados del dashboard."""

from datetime import UTC, datetime, timedelta

import pytest

from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario

CREADO = datetime(2026, 10, 1, 12, tzinfo=UTC)


@pytest.fixture
def admin(loguear):
    return loguear(TipoUsuario.ADMINISTRADOR)


def _ultimo_movimiento(client, reclamo):
    fila = next(x for x in client.get("/reclamos").json() if x["id"] == reclamo.id)
    return datetime.fromisoformat(fila["fecha_ultimo_movimiento"])


def test_es_el_ultimo_cambio_de_estado(client, admin, crear_reclamo, crear_historial):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO, fecha_creacion=CREADO)
    crear_historial(reclamo, EstadoReclamo.PENDIENTE_REVISION, CREADO)
    crear_historial(
        reclamo,
        EstadoReclamo.PENDIENTE_PRESUPUESTO,
        CREADO + timedelta(days=3),
        estado_anterior=EstadoReclamo.PENDIENTE_REVISION,
    )

    assert _ultimo_movimiento(client, reclamo) == CREADO + timedelta(days=3)


def test_sin_historial_cuenta_desde_la_creacion(client, admin, crear_reclamo):
    reclamo = crear_reclamo(fecha_creacion=CREADO)

    assert _ultimo_movimiento(client, reclamo) == CREADO
