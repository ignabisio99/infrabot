"""Una cuenta creada con Google no tiene contraseña. Entrar con email y contraseña daba 500
(bcrypt rechaza el hash vacío con ValueError); tiene que ser el 401 de siempre, y la cuenta
puede elegir una contraseña desde "¿Olvidaste tu contraseña?"."""

from unittest.mock import patch

import pytest

from core.auth import verify_password
from models.usuario import EstadoUsuario, TipoUsuario, Usuario

EMAIL = "google@ejemplo.com"
NUEVA = "ClaveNueva123!"


@pytest.fixture
def cuenta_google(db):
    usuario = Usuario(
        nombre="Cuenta Google",
        email=EMAIL,
        password_hash="",
        email_confirmado=True,
        tipo=TipoUsuario.INSPECTOR,
        estado=EstadoUsuario.APROBADO,
    )
    db.add(usuario)
    db.flush()
    return usuario


@pytest.mark.parametrize("hash_guardado", ["", None, "no-es-un-hash-de-bcrypt"])
def test_verify_password_con_un_hash_que_no_es_de_bcrypt_es_false(hash_guardado):
    assert verify_password("Cualquiera1!", hash_guardado) is False


def test_login_con_contrasena_en_cuenta_de_google_es_401(client, cuenta_google):
    r = client.post("/auth/login", json={"email": EMAIL, "password": "Cualquiera1!"})

    assert r.status_code == 401
    assert r.json()["detail"] == "Email o contraseña incorrectos"


def test_reenviar_confirmacion_en_cuenta_de_google_es_401(client, cuenta_google):
    r = client.post("/auth/reenviar-confirmacion", json={"email": EMAIL, "password": "Cualquiera1!"})

    assert r.status_code == 401


def test_la_cuenta_de_google_puede_elegir_contrasena_y_entrar(client, cuenta_google):
    with patch("api.auth.enviar_restablecer_password", return_value=True) as enviar:
        assert client.post("/auth/olvide-password", json={"email": EMAIL}).status_code == 200
    token = enviar.call_args.args[2]

    r = client.post("/auth/restablecer-password", json={"token": token, "password": NUEVA})
    assert r.status_code == 200

    assert client.post("/auth/login", json={"email": EMAIL, "password": NUEVA}).status_code == 200
