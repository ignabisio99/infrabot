"""Un reclamo que queda desierto porque el contratista dejó de responder se queda sin
contratista: su presupuesto aprobado se rechaza y la visita se cancela.

Antes el aprobado seguía en pie. Al reconvocar, la primera oferta nueva intentaba llevar
el reclamo a APROBADO y fallaba (500), la visita seguía mandando recordatorios y el
contratista que abandonó no se podía dar de baja.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import api.presupuestos
from core.dependencies import get_current_user
from main import app
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.presupuesto import EstadoPresupuesto
from models.recordatorio_contratista import RecordatorioContratista
from models.reclamo import EstadoReclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from models.visita import EstadoVisita
from services import baja_contratistas
from services.reabrir_convocatoria import liberar_aprobados_de_reclamos_sin_adjudicar
from services.seguimiento import ejecutar_seguimiento

ITEMS = [{"descripcion": "Cambio de cañería", "cantidad": "1", "costo_unitario": "5000"}]


@pytest.fixture(autouse=True)
def sin_auditoria_ia(monkeypatch):
    monkeypatch.setattr(api.presupuestos, "post_presupuesto", lambda db, p: None)


@pytest.fixture
def obra_con_visita(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista, crear_visita):
    def _crear(estado=EstadoReclamo.EN_EJECUCION):
        contratista = crear_contratista("Plomería que abandonó")
        contratista.telefono = "sim5491100005555"
        reclamo = crear_reclamo(estado=estado)
        aprobado = crear_presupuesto_aprobado(
            reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
        )
        visita = crear_visita(
            reclamo, fecha_visita=reclamo.fecha_creacion, estado=EstadoVisita.CONFIRMADA, contratista=contratista
        )
        return reclamo, aprobado, visita, contratista

    return _crear


@pytest.fixture
def ofertar(db, client, crear_contratista):
    """Un contratista convocado carga su oferta, logueado como él."""

    def _ofertar(reclamo, nombre="Plomería nueva"):
        usuario = Usuario(
            nombre=nombre,
            email=f"{nombre.lower().replace(' ', '.')}@test.local",
            password_hash="x",
            tipo=TipoUsuario.CONTRATISTA,
            estado=EstadoUsuario.APROBADO,
        )
        db.add(usuario)
        db.flush()
        ficha = crear_contratista(nombre)
        ficha.usuario_id = usuario.id
        db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=ficha.id))
        db.flush()
        app.dependency_overrides[get_current_user] = lambda: usuario
        return client.post(
            "/presupuestos", json={"reclamo_id": reclamo.id, "contratista_id": ficha.id, "items": ITEMS}
        )

    return _ofertar


@pytest.fixture
def dejar_desierto(db, monkeypatch):
    """Corre el seguimiento hasta que el reclamo pasa a desierto: una pregunta sin
    respuesta y, vencido su plazo, el cierre."""

    def _correr(reclamo):
        monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
        monkeypatch.setenv("SEGUIMIENTO_MAX_INTENTOS", "1")
        with patch("core.whatsapp_client.enviar_botones", return_value={}):
            assert ejecutar_seguimiento(db).enviados == 1
            assert ejecutar_seguimiento(db).escalados == 1
        assert reclamo.estado == EstadoReclamo.DESIERTO

    return _correr


def test_desierto_rechaza_el_aprobado_y_cancela_la_visita(db, obra_con_visita, dejar_desierto):
    reclamo, aprobado, visita, _ = obra_con_visita()

    dejar_desierto(reclamo)

    assert aprobado.estado == EstadoPresupuesto.RECHAZADO
    asiento = (
        db.query(HistorialEstadoPresupuesto)
        .filter_by(presupuesto_id=aprobado.id, estado_nuevo=EstadoPresupuesto.RECHAZADO)
        .one()
    )
    assert "no respondió" in asiento.motivo
    assert visita.estado == EstadoVisita.CANCELADA
    assert db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).count() == 0


def test_reconvocado_acepta_un_presupuesto_nuevo(
    db, client, loguear, ofertar, obra_con_visita, dejar_desierto
):
    reclamo, _, _, _ = obra_con_visita()
    dejar_desierto(reclamo)
    loguear(TipoUsuario.ADMINISTRADOR)

    r = client.post(
        f"/reclamos/{reclamo.id}/estado",
        json={"estado": "PENDIENTE_PRESUPUESTO", "motivo": "Se reconvoca"},
    )
    assert r.status_code == 200, r.text

    r = ofertar(reclamo)
    assert r.status_code == 201, r.text
    db.refresh(reclamo)
    assert reclamo.estado == EstadoReclamo.EN_EVALUACION


def test_el_contratista_que_abandono_se_puede_dar_de_baja(db, obra_con_visita, dejar_desierto):
    reclamo, _, _, contratista = obra_con_visita()
    dejar_desierto(reclamo)

    assert baja_contratistas.reclamos_en_curso(db, contratista) == []
    baja_contratistas.dar_de_baja(db, contratista)
    assert contratista.dado_de_baja


def test_al_arrancar_se_liberan_los_aprobados_que_quedaron_colgados(db, obra_con_visita):
    desierto, aprobado_desierto, visita_desierto, _ = obra_con_visita(EstadoReclamo.DESIERTO)
    reconvocado, aprobado_reconvocado, _, _ = obra_con_visita(EstadoReclamo.PENDIENTE_PRESUPUESTO)
    en_obra, aprobado_en_obra, visita_en_obra, _ = obra_con_visita(EstadoReclamo.EN_EJECUCION)
    db.add(
        RecordatorioContratista(
            reclamo_id=desierto.id, ultimo_envio=datetime.now(timezone.utc), cantidad_envios=5
        )
    )
    db.flush()

    assert liberar_aprobados_de_reclamos_sin_adjudicar(db) == 2

    assert aprobado_desierto.estado == EstadoPresupuesto.RECHAZADO
    assert aprobado_reconvocado.estado == EstadoPresupuesto.RECHAZADO
    assert visita_desierto.estado == EstadoVisita.CANCELADA
    assert db.query(RecordatorioContratista).filter_by(reclamo_id=desierto.id).count() == 0
    assert desierto.estado == EstadoReclamo.DESIERTO
    assert reconvocado.estado == EstadoReclamo.PENDIENTE_PRESUPUESTO
    # Una obra en curso conserva su contratista.
    assert aprobado_en_obra.estado == EstadoPresupuesto.APROBADO
    assert visita_en_obra.estado == EstadoVisita.CONFIRMADA

    assert liberar_aprobados_de_reclamos_sin_adjudicar(db) == 0


def test_un_estado_inconsistente_devuelve_409_y_no_500(db, ofertar, obra_con_visita):
    reclamo, _, _, _ = obra_con_visita(EstadoReclamo.PENDIENTE_PRESUPUESTO)

    r = ofertar(reclamo)
    assert r.status_code == 409
    assert "No se pudo actualizar el estado del reclamo" in r.json()["detail"]
