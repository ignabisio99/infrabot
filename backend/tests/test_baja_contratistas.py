"""Dar de baja un contratista: no se borra su historial y no se lo puede volver a convocar."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

import api.presupuestos
import api.reclamos
from models.lista_contratistas import ListaContratistas
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import TipoUsuario
from services.reabrir_convocatoria import (
    ReaperturaInvalida,
    asignar_oferta_existente,
    listar_ofertas_reutilizables,
)

ITEMS = [{"descripcion": "Membrana", "cantidad": "2", "costo_unitario": "1000"}]


@pytest.fixture
def crear_oferta(db):
    def _crear(reclamo, contratista, estado):
        presupuesto = Presupuesto(
            reclamo_id=reclamo.id, contratista_id=contratista.id, estado=estado
        )
        db.add(presupuesto)
        db.flush()
        return presupuesto

    return _crear


@pytest.fixture
def whatsapps(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        api.reclamos,
        "enviar_mensaje",
        lambda telefono, texto: enviados.append(telefono) or {"messages": [{}]},
    )
    monkeypatch.setattr(api.reclamos, "_email_del_contratista", lambda db, c: None)
    return enviados


def _dar_de_baja(client, contratista):
    return client.delete(f"/contratistas/{contratista.id}")


def _ids(respuesta):
    return {c["id"] for c in respuesta.json()}


def test_dar_de_baja_conserva_los_presupuestos_de_reclamos_cerrados(
    client, db, loguear, crear_reclamo, crear_contratista, crear_presupuesto_aprobado
):
    contratista = crear_contratista()
    reclamo = crear_reclamo(estado=EstadoReclamo.FINALIZADO)
    presupuesto = crear_presupuesto_aprobado(
        reclamo, items=[(1, 1000)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )

    assert _dar_de_baja(client, contratista).status_code == 204

    db.refresh(contratista)
    assert contratista.fecha_baja is not None
    assert db.get(Presupuesto, presupuesto.id).contratista_id == contratista.id
    loguear(TipoUsuario.ADMINISTRADOR)
    detalle = client.get(f"/presupuestos/{presupuesto.id}").json()
    assert detalle["contratista"]["nombre_empresa"] == contratista.nombre_empresa
    assert detalle["contratista"]["fecha_baja"] is not None


def test_dado_de_baja_no_aparece_en_el_listado_salvo_que_se_lo_pida(
    client, crear_contratista
):
    activo = crear_contratista("Activo SA")
    dado_de_baja = crear_contratista("Retirado SA")
    _dar_de_baja(client, dado_de_baja)

    assert _ids(client.get("/contratistas")) == {activo.id}
    assert _ids(client.get("/contratistas?incluir_baja=true")) == {activo.id, dado_de_baja.id}


def test_reactivar_lo_vuelve_al_listado(client, crear_contratista):
    contratista = crear_contratista()
    _dar_de_baja(client, contratista)

    respuesta = client.post(f"/contratistas/{contratista.id}/reactivar")

    assert respuesta.status_code == 200
    assert respuesta.json()["fecha_baja"] is None
    assert contratista.id in _ids(client.get("/contratistas"))


@pytest.mark.parametrize(
    ("estado_reclamo", "estado_presupuesto"),
    [
        (EstadoReclamo.EN_EJECUCION, EstadoPresupuesto.APROBADO),
        (EstadoReclamo.PENDIENTE_INTERVENCION, EstadoPresupuesto.APROBADO),
        (EstadoReclamo.EN_EVALUACION, EstadoPresupuesto.RECIBIDO),
        (EstadoReclamo.EN_EVALUACION, EstadoPresupuesto.AJUSTES_SOLICITADOS),
    ],
)
def test_no_se_puede_dar_de_baja_con_trabajo_en_curso(
    client, db, crear_reclamo, crear_contratista, crear_oferta, estado_reclamo, estado_presupuesto
):
    contratista = crear_contratista("Techos Sur")
    reclamo = crear_reclamo(estado=estado_reclamo)
    crear_oferta(reclamo, contratista, estado_presupuesto)

    respuesta = _dar_de_baja(client, contratista)

    assert respuesta.status_code == 409
    assert f"#{reclamo.id}" in respuesta.json()["detail"]
    assert "Techos Sur" in respuesta.json()["detail"]
    db.refresh(contratista)
    assert contratista.fecha_baja is None


def test_ofertas_que_ya_no_compiten_o_convocatorias_sin_respuesta_no_bloquean(
    client, db, crear_reclamo, crear_contratista, crear_oferta
):
    contratista = crear_contratista()
    abierto = crear_reclamo(estado=EstadoReclamo.EN_EVALUACION)
    crear_oferta(abierto, contratista, EstadoPresupuesto.RECHAZADO)
    otro_abierto = crear_reclamo(estado=EstadoReclamo.APROBADO)
    crear_oferta(otro_abierto, contratista, EstadoPresupuesto.NO_SELECCIONADO)
    cancelado = crear_reclamo(estado=EstadoReclamo.CANCELADO)
    crear_oferta(cancelado, contratista, EstadoPresupuesto.RECIBIDO)
    sin_respuesta = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    db.add(SolicitudPresupuesto(reclamo_id=sin_respuesta.id, contratista_id=contratista.id))
    db.flush()

    assert _dar_de_baja(client, contratista).status_code == 204


def test_borrar_la_fila_con_historial_lo_impide_la_base(
    db, crear_reclamo, crear_contratista, crear_oferta
):
    contratista = crear_contratista()
    crear_oferta(
        crear_reclamo(estado=EstadoReclamo.FINALIZADO), contratista, EstadoPresupuesto.APROBADO
    )

    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(contratista)
        db.flush()


def test_no_se_lo_puede_convocar(client, whatsapps, crear_reclamo, crear_contratista):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    activo = crear_contratista("Activo SA")
    dado_de_baja = crear_contratista("Retirado SA")
    _dar_de_baja(client, dado_de_baja)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-contratistas",
        json={"contratista_ids": [activo.id, dado_de_baja.id]},
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "No se puede convocar a Retirado SA: está dado de baja"
    assert whatsapps == []


def test_al_usar_una_lista_se_saltea_a_los_dados_de_baja(
    client, db, whatsapps, crear_reclamo, crear_contratista
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    activo = crear_contratista("Activo SA")
    activo.telefono = "5491100000001"
    dado_de_baja = crear_contratista("Retirado SA")
    dado_de_baja.telefono = "5491100000002"
    lista = ListaContratistas(nombre="Techistas", contratistas=[activo, dado_de_baja])
    db.add(lista)
    db.flush()
    _dar_de_baja(client, dado_de_baja)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-contratistas", json={"lista_id": lista.id}
    )

    assert respuesta.status_code == 200
    assert [r["contratista_id"] for r in respuesta.json()["resultados"]] == [activo.id]
    assert whatsapps == ["5491100000001"]
    db.refresh(lista)
    assert dado_de_baja in lista.contratistas


def test_una_lista_con_todos_dados_de_baja_no_notifica_a_nadie(
    client, db, whatsapps, crear_reclamo, crear_contratista
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    dado_de_baja = crear_contratista("Retirado SA")
    lista = ListaContratistas(nombre="Viejos", contratistas=[dado_de_baja])
    db.add(lista)
    db.flush()
    _dar_de_baja(client, dado_de_baja)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-contratistas", json={"lista_id": lista.id}
    )

    assert respuesta.status_code == 422
    assert "dados de baja" in respuesta.json()["detail"]
    assert whatsapps == []


def test_su_cuenta_ve_las_convocatorias_pero_no_puede_ofertar(
    client, monkeypatch, crear_reclamo, loguear_contratista_convocado
):
    monkeypatch.setattr(api.presupuestos, "post_presupuesto", lambda db, p: None)
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista_convocado(reclamo, nombre="Retirado SA")
    ficha.fecha_baja = datetime.now(UTC)

    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["reclamo_id"] == reclamo.id
    assert solicitud["puede_ofertar"] is False

    respuesta = client.post(
        "/presupuestos",
        json={"reclamo_id": reclamo.id, "contratista_id": ficha.id, "items": ITEMS},
    )
    assert respuesta.status_code == 409
    assert client.get("/contratistas/mi-ficha").json()["fecha_baja"] is not None


def test_la_convocatoria_del_reclamo_lo_muestra_como_dado_de_baja(
    client, db, crear_reclamo, crear_contratista
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    contratista = crear_contratista()
    db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=contratista.id))
    db.flush()
    _dar_de_baja(client, contratista)

    [solicitud] = client.get(f"/reclamos/{reclamo.id}/solicitudes-presupuesto").json()

    assert solicitud["contratista_dado_de_baja"] is True


@patch("services.reabrir_convocatoria.enviar_mensaje")
def test_no_se_puede_reasignar_a_una_oferta_de_un_dado_de_baja(
    _enviar, db, crear_reclamo, crear_contratista, crear_presupuesto_aprobado, crear_oferta
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_INTERVENCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion
    )
    otra = crear_oferta(reclamo, crear_contratista("Otra SA"), EstadoPresupuesto.NO_SELECCIONADO)
    retirado = crear_contratista("Retirado SA")
    oferta_retirado = crear_oferta(reclamo, retirado, EstadoPresupuesto.NO_SELECCIONADO)
    retirado.fecha_baja = datetime.now(UTC)
    db.flush()

    assert [o.presupuesto_id for o in listar_ofertas_reutilizables(db, reclamo)] == [otra.id]
    with pytest.raises(ReaperturaInvalida, match="Retirado SA está dado de baja"):
        asignar_oferta_existente(db, reclamo, oferta_retirado.id)
