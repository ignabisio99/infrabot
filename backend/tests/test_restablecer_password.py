"""Recuperar contraseña: pedido por email, link de un solo uso que vence, contraseña nueva."""

from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from core.auth import create_access_token, hash_password, verify_password
from models.usuario import EstadoUsuario, TipoUsuario, Usuario

NUEVA = "OtraClave123!"


@pytest.fixture
def usuario(db):
    usuario = Usuario(
        nombre="Ana",
        email="ana@ejemplo.com",
        password_hash=hash_password("ClaveVieja1!"),
        email_confirmado=True,
        tipo=TipoUsuario.INSPECTOR,
        estado=EstadoUsuario.APROBADO,
    )
    db.add(usuario)
    db.flush()
    return usuario


def _pedir_link(client, email):
    """Pide el link y devuelve el token que viajó en el email (o None si no se mandó)."""
    with patch("api.auth.enviar_restablecer_password", return_value=True) as enviar:
        respuesta = client.post("/auth/olvide-password", json={"email": email})
    assert respuesta.status_code == 200
    if not enviar.called:
        return None
    return enviar.call_args.args[2]


def test_pide_el_link_y_cambia_la_contrasena(client, usuario):
    token = _pedir_link(client, "ana@ejemplo.com")

    assert client.get("/auth/restablecer-password", params={"token": token}).json() == {
        "email": "ana@ejemplo.com"
    }
    respuesta = client.post("/auth/restablecer-password", json={"token": token, "password": NUEVA})

    assert respuesta.status_code == 200
    assert verify_password(NUEVA, usuario.password_hash)


def test_el_link_del_email_apunta_a_la_pantalla_de_restablecer(usuario):
    from core import email

    with patch("core.email.enviar_email", return_value=True) as enviar:
        email.enviar_restablecer_password("ana@ejemplo.com", "Ana", "abc.def")

    html = enviar.call_args.args[2]
    link = next(p for p in html.split('"') if "restablecer-password" in p)
    assert urlparse(link).path == "/restablecer-password"
    assert parse_qs(urlparse(link).query)["token"] == ["abc.def"]


def test_misma_respuesta_si_el_email_no_existe(client, usuario):
    with patch("api.auth.enviar_restablecer_password") as enviar:
        existe = client.post("/auth/olvide-password", json={"email": "ana@ejemplo.com"}).json()
        no_existe = client.post("/auth/olvide-password", json={"email": "nadie@ejemplo.com"}).json()

    assert existe == no_existe
    assert enviar.call_count == 1


def test_el_link_sirve_una_sola_vez(client, usuario):
    token = _pedir_link(client, "ana@ejemplo.com")
    client.post("/auth/restablecer-password", json={"token": token, "password": NUEVA})

    otra_vez = client.post(
        "/auth/restablecer-password", json={"token": token, "password": "Tercera123!"}
    )

    assert otra_vez.status_code == 400
    assert client.get("/auth/restablecer-password", params={"token": token}).status_code == 400
    assert verify_password(NUEVA, usuario.password_hash)


def test_un_link_vencido_no_sirve(client, usuario):
    from api.auth import _huella_password

    vencido = create_access_token(
        {"sub": str(usuario.id), "tipo": "restablecer_password", "huella": _huella_password(usuario)},
        expira_en=timedelta(seconds=-1),
    )

    respuesta = client.post("/auth/restablecer-password", json={"token": vencido, "password": NUEVA})

    assert respuesta.status_code == 400
    assert "venció" in respuesta.json()["detail"]


def test_otro_tipo_de_token_no_sirve(client, usuario):
    # Ni el de confirmación de email ni el de sesión.
    for datos in ({"sub": str(usuario.id), "tipo": "confirmacion"}, {"sub": str(usuario.id)}):
        token = create_access_token(datos)
        respuesta = client.post("/auth/restablecer-password", json={"token": token, "password": NUEVA})
        assert respuesta.status_code == 400


def test_la_contrasena_nueva_cumple_las_mismas_reglas_que_al_registrarse(client, usuario):
    token = _pedir_link(client, "ana@ejemplo.com")

    respuesta = client.post("/auth/restablecer-password", json={"token": token, "password": "corta"})

    assert respuesta.status_code == 422
    assert not verify_password("corta", usuario.password_hash)


def test_restablecer_confirma_el_email(client, usuario):
    usuario.email_confirmado = False
    token = _pedir_link(client, "ana@ejemplo.com")

    client.post("/auth/restablecer-password", json={"token": token, "password": NUEVA})

    assert usuario.email_confirmado is True
