import pytest
from fastapi import HTTPException

from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario
from services.ai import agente, auditoria, clasificacion, duplicados, estimacion, grafo, vision_reclamo

ESTADOS_CERRADOS = [EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO]

# (método, ruta, módulo y función de IA que dispara)
ACCIONES_SOBRE_RECLAMO = [
    ("post", "/ai/reclamos/{id}/clasificar?aplicar=true", clasificacion, "clasificar_reclamo"),
    ("post", "/ai/reclamos/{id}/estimacion", estimacion, "generar_estimacion"),
    ("post", "/ai/reclamos/{id}/orquestar", grafo, "ejecutar_pipeline"),
    ("post", "/ai/reclamos/{id}/analizar-agente", agente, "analizar_reclamo"),
    ("post", "/ai/reclamos/{id}/analizar-media", vision_reclamo, "analizar_media_reclamo"),
]


@pytest.fixture
def llamadas_ia(monkeypatch):
    """Reemplaza los servicios de IA por uno que anota la llamada y corta el request.

    Así los tests no dependen de un proveedor real: alcanza con saber si el endpoint
    llegó a llamar a la IA o la validación lo frenó antes.
    """
    llamadas = []

    def falso(nombre):
        def _llamar(*_args, **_kwargs):
            llamadas.append(nombre)
            raise HTTPException(status_code=418, detail="IA de prueba")

        return _llamar

    for _metodo, _ruta, modulo, funcion in ACCIONES_SOBRE_RECLAMO:
        monkeypatch.setattr(modulo, funcion, falso(funcion))
    monkeypatch.setattr(auditoria, "auditar_presupuesto", falso("auditar_presupuesto"))
    return llamadas


@pytest.fixture
def crear_presupuesto(db, crear_contratista):
    def _crear(reclamo):
        presupuesto = Presupuesto(
            reclamo_id=reclamo.id,
            contratista_id=crear_contratista().id,
            estado=EstadoPresupuesto.RECIBIDO,
        )
        db.add(presupuesto)
        db.flush()
        return presupuesto

    return _crear


@pytest.mark.parametrize("estado", ESTADOS_CERRADOS)
@pytest.mark.parametrize(("metodo", "ruta", "_modulo", "_funcion"), ACCIONES_SOBRE_RECLAMO)
def test_no_se_vuelve_a_analizar_un_reclamo_cerrado(
    client, crear_reclamo, llamadas_ia, estado, metodo, ruta, _modulo, _funcion
):
    reclamo = crear_reclamo(estado=estado)

    respuesta = getattr(client, metodo)(ruta.format(id=reclamo.id))

    assert respuesta.status_code == 409
    assert estado.etiqueta in respuesta.json()["detail"]
    assert llamadas_ia == []


@pytest.mark.parametrize(("metodo", "ruta", "_modulo", "funcion"), ACCIONES_SOBRE_RECLAMO)
def test_un_reclamo_abierto_se_sigue_analizando(
    client, crear_reclamo, llamadas_ia, metodo, ruta, _modulo, funcion
):
    # DESIERTO no es final: se puede volver a llamar a presupuesto.
    reclamo = crear_reclamo(estado=EstadoReclamo.DESIERTO)

    respuesta = getattr(client, metodo)(ruta.format(id=reclamo.id))

    assert respuesta.status_code != 409
    assert llamadas_ia == [funcion]


@pytest.mark.parametrize("estado", ESTADOS_CERRADOS)
def test_no_se_audita_un_presupuesto_de_un_reclamo_cerrado(
    client, loguear, crear_reclamo, crear_presupuesto, llamadas_ia, estado
):
    presupuesto = crear_presupuesto(crear_reclamo(estado=estado))
    loguear(TipoUsuario.ADMINISTRADOR)

    respuesta = client.post(f"/ai/presupuestos/{presupuesto.id}/auditar")

    assert respuesta.status_code == 409
    assert estado.etiqueta in respuesta.json()["detail"]
    assert llamadas_ia == []


def test_se_audita_un_presupuesto_de_un_reclamo_abierto(
    client, loguear, crear_reclamo, crear_presupuesto, llamadas_ia
):
    presupuesto = crear_presupuesto(crear_reclamo(estado=EstadoReclamo.EN_EVALUACION))
    loguear(TipoUsuario.ADMINISTRADOR)

    client.post(f"/ai/presupuestos/{presupuesto.id}/auditar")

    assert llamadas_ia == ["auditar_presupuesto"]


@pytest.mark.parametrize("estado", ESTADOS_CERRADOS)
def test_un_reclamo_cerrado_sigue_mostrando_duplicados(
    client, crear_reclamo, monkeypatch, estado
):
    # El panel de IA los pide al abrir cualquier reclamo, cerrado o no.
    monkeypatch.setattr(duplicados, "buscar_duplicados", lambda _db, _reclamo: [])
    reclamo = crear_reclamo(estado=estado)

    respuesta = client.get(f"/ai/reclamos/{reclamo.id}/duplicados")

    assert respuesta.status_code == 200
    assert respuesta.json()["candidatos"] == []
