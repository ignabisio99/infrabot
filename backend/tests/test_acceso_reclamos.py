"""Un contratista solo ve y presupuesta los reclamos a los que lo convocaron."""

import pytest

from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario

ITEMS = [{"descripcion": "Membrana", "cantidad": "2", "costo_unitario": "1000"}]


def _ofertar(client, reclamo, ficha):
    return client.post(
        "/presupuestos",
        json={"reclamo_id": reclamo.id, "contratista_id": ficha.id, "items": ITEMS},
    )


def test_no_puede_presupuestar_un_reclamo_al_que_no_lo_convocaron(
    client, crear_reclamo, loguear_contratista_convocado
):
    convocado = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ajeno = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista_convocado(convocado)

    respuesta = _ofertar(client, ajeno, ficha)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "No fuiste convocado a presupuestar este reclamo."
    assert _ofertar(client, convocado, ficha).status_code == 201


def test_solo_lista_los_reclamos_a_los_que_lo_convocaron(
    client, crear_reclamo, loguear_contratista_convocado
):
    convocado = crear_reclamo()
    crear_reclamo()
    loguear_contratista_convocado(convocado)

    assert [r["id"] for r in client.get("/reclamos").json()] == [convocado.id]


@pytest.mark.parametrize(
    "ruta", ["", "/historial", "/comentarios", "/visita"], ids=["detalle", "historial", "comentarios", "visita"]
)
def test_no_ve_un_reclamo_ajeno_aunque_sepa_el_id(
    client, crear_reclamo, loguear_contratista_convocado, ruta
):
    convocado = crear_reclamo()
    ajeno = crear_reclamo()
    loguear_contratista_convocado(convocado)

    assert client.get(f"/reclamos/{ajeno.id}{ruta}").status_code == 403
    assert client.get(f"/reclamos/{convocado.id}{ruta}").status_code == 200


def test_no_pide_informacion_de_un_reclamo_ajeno(
    client, crear_reclamo, loguear_contratista_convocado
):
    convocado = crear_reclamo(telefono_creador="5491100000000")
    ajeno = crear_reclamo(telefono_creador="5491100000001")
    loguear_contratista_convocado(convocado)

    respuesta = client.post(
        f"/reclamos/{ajeno.id}/solicitar-informacion", json={"mensaje": "¿Medidas del aula?"}
    )

    assert respuesta.status_code == 403


def test_contratista_sin_ficha_no_ve_reclamos(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.CONTRATISTA)

    assert client.get("/reclamos").json() == []
    assert client.get(f"/reclamos/{reclamo.id}").status_code == 403


@pytest.mark.parametrize("tipo", [TipoUsuario.ADMINISTRADOR, TipoUsuario.INSPECTOR])
def test_admin_e_inspector_ven_todos(client, loguear, crear_reclamo, tipo):
    reclamos = [crear_reclamo(), crear_reclamo()]
    loguear(tipo)

    ids = {r["id"] for r in client.get("/reclamos").json()}
    assert {r.id for r in reclamos} <= ids
    assert client.get(f"/reclamos/{reclamos[0].id}").status_code == 200
