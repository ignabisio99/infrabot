"""Una cuenta rechazada queda bloqueada: se le avisa por email y no entra por ningún medio."""

from unittest.mock import patch

import pytest

from core.auth import hash_password
from models.usuario import EstadoUsuario, TipoUsuario, Usuario

EMAIL = "rechazada@ejemplo.com"
PASSWORD = "Clave123!"


@pytest.fixture
def pendiente(db):
    usuario = Usuario(
        nombre="Rechazada",
        email=EMAIL,
        password_hash=hash_password(PASSWORD),
        email_confirmado=True,
        tipo=TipoUsuario.INSPECTOR,
        estado=EstadoUsuario.PENDIENTE_APROBACION,
    )
    db.add(usuario)
    db.flush()
    return usuario


@pytest.fixture
def rechazada(client, pendiente):
    with patch("api.auth.enviar_rechazo_cuenta", return_value=True):
        client.post(f"/auth/rechazar/{pendiente.id}")
    return pendiente


def test_rechazar_avisa_por_email(client, pendiente):
    with patch("api.auth.enviar_rechazo_cuenta", return_value=True) as enviar:
        respuesta = client.post(f"/auth/rechazar/{pendiente.id}")

    assert respuesta.status_code == 200
    assert pendiente.estado == EstadoUsuario.RECHAZADO
    enviar.assert_called_once_with(EMAIL)


def test_no_entra_con_email_y_contrasena(client, rechazada):
    respuesta = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert respuesta.status_code == 403
    assert "rechazada" in respuesta.json()["detail"]


def test_no_entra_con_google(client, rechazada):
    with patch("api.auth.id_token.verify_oauth2_token", return_value={"email": EMAIL}):
        respuesta = client.post("/auth/google", json={"credential": "x"})

    assert respuesta.status_code == 403
    assert "rechazada" in respuesta.json()["detail"]
    assert "set-cookie" not in respuesta.headers


def test_no_puede_volver_a_pedir_la_cuenta(client, rechazada):
    with patch("api.auth.enviar_confirmacion", return_value=True):
        respuesta = client.post(
            "/auth/register",
            json={
                "nombre": "Otra vez",
                "email": EMAIL,
                "password": PASSWORD,
                "telefono": "1155556666",
                "direccion": "Calle Falsa 123",
                "tipo": "INSPECTOR",
            },
        )

    assert respuesta.status_code == 409
    assert "rechazada" in respuesta.json()["detail"]
    assert rechazada.estado == EstadoUsuario.RECHAZADO
