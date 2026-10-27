"""Un email = una cuenta, sin importar mayúsculas: ni por registro ni por Google."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from core.auth import hash_password
from models.usuario import EstadoUsuario, TipoUsuario, Usuario

PASSWORD = "Clave123!"


def _registrar(client, email):
    with patch("api.auth.enviar_confirmacion", return_value=True):
        return client.post(
            "/auth/register",
            json={
                "nombre": "Juan",
                "email": email,
                "password": PASSWORD,
                "telefono": "1155556666",
                "direccion": "Calle Falsa 123",
                "tipo": "INSPECTOR",
            },
        )


def _cuentas(db, email):
    return db.query(Usuario).filter(Usuario.email.ilike(email)).all()


def test_el_email_se_guarda_en_minusculas(client, db):
    assert _registrar(client, "Juan.Perez@Ejemplo.com").status_code == 201

    [cuenta] = _cuentas(db, "juan.perez@ejemplo.com")
    assert cuenta.email == "juan.perez@ejemplo.com"


def test_no_se_registra_dos_veces_el_mismo_email_con_otra_mayuscula(client, db):
    _registrar(client, "juan@ejemplo.com")

    respuesta = _registrar(client, "JUAN@Ejemplo.com")

    assert respuesta.status_code == 409
    assert len(_cuentas(db, "juan@ejemplo.com")) == 1


def test_google_entra_a_la_cuenta_registrada_aunque_cambien_las_mayusculas(client, db):
    _registrar(client, "Juan@Ejemplo.com")

    with patch("api.auth.id_token.verify_oauth2_token", return_value={"email": "juan@ejemplo.com"}):
        client.post("/auth/google", json={"credential": "x"})

    assert len(_cuentas(db, "juan@ejemplo.com")) == 1


def test_el_login_no_distingue_mayusculas(client, db):
    db.add(
        Usuario(
            nombre="Ana",
            email="ana@ejemplo.com",
            password_hash=hash_password(PASSWORD),
            email_confirmado=True,
            tipo=TipoUsuario.INSPECTOR,
            estado=EstadoUsuario.APROBADO,
        )
    )
    db.flush()

    respuesta = client.post("/auth/login", json={"email": "ANA@Ejemplo.COM", "password": PASSWORD})

    assert respuesta.status_code == 200


def test_encuentra_una_cuenta_vieja_guardada_con_mayusculas(client, db):
    """Cuentas creadas antes de normalizar: la búsqueda no distingue mayúsculas."""
    db.add(
        Usuario(
            nombre="Viejo",
            email="Viejo@Ejemplo.com",
            password_hash=hash_password(PASSWORD),
            email_confirmado=True,
            tipo=TipoUsuario.INSPECTOR,
            estado=EstadoUsuario.APROBADO,
        )
    )
    db.flush()

    assert client.post("/auth/login", json={"email": "viejo@ejemplo.com", "password": PASSWORD}).status_code == 200
    assert _registrar(client, "viejo@ejemplo.com").status_code == 409


def test_la_base_no_acepta_dos_cuentas_con_el_mismo_email_en_otra_mayuscula(db):
    """Última barrera, por si algún camino del código no normalizara."""
    db.add(Usuario(nombre="A", email="mismo@ejemplo.com", password_hash="x"))
    db.flush()
    db.add(Usuario(nombre="B", email="MISMO@ejemplo.com", password_hash="x"))

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
