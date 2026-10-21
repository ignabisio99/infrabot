import pytest

from core.dependencies import get_current_admin
from main import app
from models.usuario import EstadoUsuario, TipoUsuario, Usuario


@pytest.fixture
def auth_real(client, monkeypatch):
    """Saca el override de admin que pone `client`, para probar el chequeo de rol real."""
    monkeypatch.delitem(app.dependency_overrides, get_current_admin)


def _crear_usuario(db, nombre, tipo, estado=EstadoUsuario.APROBADO):
    usuario = Usuario(
        nombre=nombre,
        email=f"{nombre.lower().replace(' ', '-')}@test.local",
        password_hash="x",
        tipo=tipo,
        estado=estado,
    )
    db.add(usuario)
    db.flush()
    return usuario


def test_lista_solo_administradores_aprobados_ordenados_por_nombre(client, db):
    _crear_usuario(db, "Zoe Admin", TipoUsuario.ADMINISTRADOR)
    _crear_usuario(db, "Ana Admin", TipoUsuario.ADMINISTRADOR)
    _crear_usuario(db, "Pendiente Admin", TipoUsuario.ADMINISTRADOR, EstadoUsuario.PENDIENTE_APROBACION)
    _crear_usuario(db, "Rechazado Admin", TipoUsuario.ADMINISTRADOR, EstadoUsuario.RECHAZADO)
    _crear_usuario(db, "Contratista", TipoUsuario.CONTRATISTA)
    _crear_usuario(db, "Inspector", TipoUsuario.INSPECTOR)

    respuesta = client.get("/auth/administradores")

    assert respuesta.status_code == 200
    assert [u["nombre"] for u in respuesta.json()] == ["Ana Admin", "Zoe Admin"]


def test_no_expone_el_hash_de_la_contrasena(client, db):
    _crear_usuario(db, "Ana Admin", TipoUsuario.ADMINISTRADOR)

    administrador = client.get("/auth/administradores").json()[0]

    assert "password_hash" not in administrador
    assert administrador["email"] == "ana-admin@test.local"


def test_rechaza_a_quien_no_es_administrador(client, auth_real, loguear):
    loguear(TipoUsuario.CONTRATISTA)

    respuesta = client.get("/auth/administradores")

    assert respuesta.status_code == 403


def test_rechaza_sin_sesion(client, auth_real):
    respuesta = client.get("/auth/administradores")

    assert respuesta.status_code == 401
