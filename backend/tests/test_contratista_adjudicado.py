"""El que hace la obra es el contratista del presupuesto aprobado, no el último que ofertó.

Caso real: se aprueba la oferta de Electricidad y Plomería había mandado la suya después.
Con "el presupuesto más reciente", la pregunta de avance, el aviso de cierre y el
reconocimiento del teléfono le tocaban a Plomería.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest

from api.simulador_tiempo import _construir_estado
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo
from services.avance_contratista import mismo_numero, reclamo_en_ejecucion_de
from services.coordinacion_visita import contratista_de_reclamo_coordinado
from services.estados_presupuesto import contratista_adjudicado
from services.resolucion_escuela import registrar_resolucion
from services.seguimiento import ejecutar_seguimiento

TEL_GANADOR = "sim5491100002222"
TEL_PERDEDOR = "sim5491100003333"


@pytest.fixture
def reclamo_con_perdedor_posterior(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    def _crear(estado):
        reclamo = crear_reclamo(estado=estado, telefono_creador="sim5491100004444")
        ganador = crear_contratista("Electricidad del Sur")
        ganador.telefono = TEL_GANADOR
        perdedor = crear_contratista("Plomería Norte")
        perdedor.telefono = TEL_PERDEDOR
        aprobado = crear_presupuesto_aprobado(
            reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=ganador
        )
        db.add(
            Presupuesto(
                reclamo_id=reclamo.id,
                contratista_id=perdedor.id,
                estado=EstadoPresupuesto.NO_SELECCIONADO,
                fecha=aprobado.fecha + timedelta(hours=1),
            )
        )
        db.flush()
        return reclamo, ganador, perdedor

    return _crear


def test_contratista_adjudicado_es_el_del_aprobado(db, reclamo_con_perdedor_posterior):
    reclamo, ganador, _ = reclamo_con_perdedor_posterior(EstadoReclamo.EN_EJECUCION)
    assert contratista_adjudicado(db, reclamo.id).id == ganador.id


def test_sin_presupuesto_aprobado_no_hay_adjudicado(db, crear_reclamo, crear_contratista):
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EVALUACION)
    db.add(
        Presupuesto(
            reclamo_id=reclamo.id,
            contratista_id=crear_contratista().id,
            estado=EstadoPresupuesto.RECIBIDO,
        )
    )
    db.flush()
    assert contratista_adjudicado(db, reclamo.id) is None


def test_en_ejecucion_reconoce_al_ganador_y_no_al_perdedor(db, reclamo_con_perdedor_posterior):
    reclamo, ganador, _ = reclamo_con_perdedor_posterior(EstadoReclamo.EN_EJECUCION)

    hallado = reclamo_en_ejecucion_de(db, TEL_GANADOR)
    assert hallado is not None
    assert hallado[0].id == reclamo.id
    assert hallado[1].id == ganador.id
    assert reclamo_en_ejecucion_de(db, TEL_PERDEDOR) is None


def test_visita_coordinada_reconoce_al_ganador_y_no_al_perdedor(db, reclamo_con_perdedor_posterior):
    reclamo, ganador, _ = reclamo_con_perdedor_posterior(EstadoReclamo.VISITA_COORDINADA)

    hallado = contratista_de_reclamo_coordinado(db, TEL_GANADOR)
    assert hallado is not None
    assert hallado[1].id == ganador.id
    assert contratista_de_reclamo_coordinado(db, TEL_PERDEDOR) is None


@patch("core.whatsapp_client.enviar_botones")
def test_seguimiento_le_pregunta_al_ganador(mock_botones, db, reclamo_con_perdedor_posterior, monkeypatch):
    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    mock_botones.return_value = {}
    reclamo_con_perdedor_posterior(EstadoReclamo.EN_EJECUCION)

    assert ejecutar_seguimiento(db).enviados == 1
    destino, cuerpo = mock_botones.call_args.args[:2]
    assert mismo_numero(destino, TEL_GANADOR)
    assert "Electricidad del Sur" in cuerpo


@patch("core.whatsapp_client.enviar_mensaje")
def test_aviso_de_cierre_le_llega_al_ganador(mock_mensaje, db, reclamo_con_perdedor_posterior):
    reclamo, _, _ = reclamo_con_perdedor_posterior(EstadoReclamo.EN_EJECUCION)

    assert registrar_resolucion(db, reclamo, avisar_escuela=False) is True
    destinos = [c.args[0] for c in mock_mensaje.call_args_list]
    assert destinos == [TEL_GANADOR]


def test_panel_del_simulador_muestra_al_ganador(db, reclamo_con_perdedor_posterior):
    reclamo, _, _ = reclamo_con_perdedor_posterior(EstadoReclamo.EN_EJECUCION)

    fila = next(r for r in _construir_estado(db).reclamos_en_ejecucion if r.id == reclamo.id)
    assert fila.contratista == "Electricidad del Sur"
    assert fila.contratista_telefono == TEL_GANADOR
