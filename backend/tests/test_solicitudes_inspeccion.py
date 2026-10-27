"""Pedidos de información a inspectores: aviso por WhatsApp y email, bandeja del inspector
y cierre cuando aporta un comentario o una foto."""

import io
from unittest.mock import patch

import pytest

from core.dependencies import get_current_admin, get_current_user
from main import app
from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario


@pytest.fixture
def avisos():
    """Mockea WhatsApp y email, y devuelve los mocks para mirar qué se mandó."""
    with patch(
        "core.whatsapp_client.enviar_mensaje", return_value={"messages": [{"id": "x"}]}
    ) as whatsapp, patch("core.email.enviar_solicitud_inspeccion", return_value=True) as email:
        yield whatsapp, email


def _como_admin(loguear):
    admin = loguear(TipoUsuario.ADMINISTRADOR, nombre="Laura")
    app.dependency_overrides[get_current_admin] = lambda: admin
    return admin


def _como(usuario):
    """Deja de actuar como admin y pasa a ser `usuario` (ej. el inspector)."""
    app.dependency_overrides.pop(get_current_admin, None)
    app.dependency_overrides[get_current_user] = lambda: usuario


def test_el_admin_pide_informacion_y_le_llega_por_whatsapp_email_y_app(
    client, loguear, crear_reclamo, avisos
):
    whatsapp, email = avisos
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EVALUACION, nombre_escuela="Escuela 5")
    inspector = loguear(TipoUsuario.INSPECTOR, nombre="Ana")
    inspector.telefono = "5491100001111"
    _como_admin(loguear)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores",
        json={"inspector_ids": [inspector.id], "mensaje": "Fotos del tablero"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["resultados"] == [
        {"inspector_id": inspector.id, "nombre": "Ana", "whatsapp": True, "email": True}
    ]
    texto = whatsapp.call_args.args[1]
    assert f"reclamo #{reclamo.id}" in texto and "Fotos del tablero" in texto
    assert f"/reclamos?abrir={reclamo.id}" in texto
    assert email.call_args.args[0] == inspector.email

    _como(inspector)
    [pendiente] = client.get("/reclamos/inspeccion/pendientes").json()
    assert pendiente["reclamo_id"] == reclamo.id
    assert pendiente["nombre_escuela"] == "Escuela 5"
    assert pendiente["mensaje"] == "Fotos del tablero"
    assert pendiente["solicitado_por_nombre"] == "Laura"


def test_sin_telefono_igual_queda_el_aviso_por_email_y_en_la_app(
    client, loguear, crear_reclamo, avisos
):
    reclamo = crear_reclamo()
    inspector = loguear(TipoUsuario.INSPECTOR)
    _como_admin(loguear)

    [resultado] = client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [inspector.id]}
    ).json()["resultados"]

    assert resultado["whatsapp"] is False
    assert resultado["email"] is True
    assert len(client.get(f"/reclamos/{reclamo.id}/solicitudes-inspeccion").json()) == 1


def test_volver_a_pedir_no_duplica_el_pedido_pendiente(client, loguear, crear_reclamo, avisos):
    reclamo = crear_reclamo()
    inspector = loguear(TipoUsuario.INSPECTOR)
    _como_admin(loguear)
    url = f"/reclamos/{reclamo.id}/notificar-inspectores"

    client.post(url, json={"inspector_ids": [inspector.id], "mensaje": "Primero"})
    client.post(url, json={"inspector_ids": [inspector.id], "mensaje": "Segundo"})

    [solicitud] = client.get(f"/reclamos/{reclamo.id}/solicitudes-inspeccion").json()
    assert solicitud["mensaje"] == "Segundo"


@pytest.mark.parametrize("aporte", ["comentario", "foto"])
def test_comentar_o_subir_una_foto_atiende_el_pedido(
    client, loguear, crear_reclamo, avisos, aporte
):
    reclamo = crear_reclamo()
    inspector = loguear(TipoUsuario.INSPECTOR)
    _como_admin(loguear)
    client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [inspector.id]}
    )
    _como(inspector)

    if aporte == "comentario":
        client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Revisado"})
    else:
        with patch("core.storage.storage.guardar", return_value="/uploads/x.jpg"), patch(
            "api.reclamos.post_fotos_reclamo"
        ):
            client.post(
                f"/reclamos/{reclamo.id}/fotos",
                files={"archivo": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")},
            )

    assert client.get("/reclamos/inspeccion/pendientes").json() == []
    [solicitud] = client.get(f"/reclamos/{reclamo.id}/solicitudes-inspeccion").json()
    assert solicitud["atendida_en"] is not None


def test_no_se_pide_informacion_de_un_reclamo_cerrado(client, loguear, crear_reclamo, avisos):
    reclamo = crear_reclamo(estado=EstadoReclamo.FINALIZADO)
    inspector = loguear(TipoUsuario.INSPECTOR)
    _como_admin(loguear)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [inspector.id]}
    )

    assert respuesta.status_code == 409


def test_solo_se_puede_elegir_inspectores_aprobados(client, loguear, crear_reclamo, avisos):
    reclamo = crear_reclamo()
    contratista = loguear(TipoUsuario.CONTRATISTA)
    _como_admin(loguear)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [contratista.id]}
    )

    assert respuesta.status_code == 404


def test_el_inspector_solo_ve_sus_pedidos_y_no_puede_pedir(
    client, loguear, crear_reclamo, avisos
):
    reclamo = crear_reclamo()
    ana = loguear(TipoUsuario.INSPECTOR, nombre="Ana")
    beto = loguear(TipoUsuario.INSPECTOR, nombre="Beto")
    _como_admin(loguear)
    client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores",
        json={"inspector_ids": [ana.id, beto.id]},
    )
    _como(beto)

    propios = client.get(f"/reclamos/{reclamo.id}/solicitudes-inspeccion").json()
    assert [s["inspector_nombre"] for s in propios] == ["Beto"]
    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [ana.id]}
    )
    assert respuesta.status_code == 403


def test_los_pedidos_de_reclamos_cerrados_no_figuran_como_pendientes(
    client, loguear, crear_reclamo, avisos
):
    reclamo = crear_reclamo()
    inspector = loguear(TipoUsuario.INSPECTOR)
    _como_admin(loguear)
    client.post(
        f"/reclamos/{reclamo.id}/notificar-inspectores", json={"inspector_ids": [inspector.id]}
    )
    reclamo.estado = EstadoReclamo.CANCELADO
    _como(inspector)

    assert client.get("/reclamos/inspeccion/pendientes").json() == []


def test_listado_de_inspectores_aprobados(client, loguear):
    loguear(TipoUsuario.INSPECTOR, nombre="Zoe")
    loguear(TipoUsuario.INSPECTOR, nombre="Ana")
    loguear(TipoUsuario.CONTRATISTA, nombre="Constructora")

    nombres = [u["nombre"] for u in client.get("/auth/inspectores").json()]

    assert nombres == ["Ana", "Zoe"]
