"""Una cuenta sin aprobar (o rechazada) no usa la API aunque tenga la sesión abierta.

Estos tests van con la cookie de sesión real, sin pisar las dependencias de auth: lo que
se prueba es justamente esa validación.
"""

import pytest

from core.auth import create_access_token, hash_password
from core.dependencies import COOKIE_NAME, get_current_admin
from main import app
from models.usuario import EstadoUsuario, TipoUsuario, Usuario


@pytest.fixture
def sesion(client, db):
    """Crea un usuario con ese tipo y estado y deja su cookie de sesión en el cliente."""
    # El fixture `client` resuelve el admin a mano: acá tiene que pasar por la validación.
    app.dependency_overrides.pop(get_current_admin, None)

    def _sesion(tipo, estado):
        usuario = Usuario(
            nombre="Prueba",
            email=f"{tipo.value.lower()}-{estado.value.lower()}@ejemplo.com",
            password_hash=hash_password("Clave123!"),
            email_confirmado=True,
            tipo=tipo,
            estado=estado,
        )
        db.add(usuario)
        db.flush()
        client.cookies.set(COOKIE_NAME, create_access_token({"sub": str(usuario.id)}))
        return usuario

    return _sesion


SIN_APROBAR = [EstadoUsuario.PENDIENTE_APROBACION, EstadoUsuario.PENDIENTE_PERFIL]


@pytest.mark.parametrize("estado", SIN_APROBAR)
def test_inspector_sin_aprobar_no_ve_reclamos_ni_comenta(client, sesion, crear_reclamo, estado):
    reclamo = crear_reclamo()
    sesion(TipoUsuario.INSPECTOR, estado)

    listado = client.get("/reclamos")
    comentario = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Hola"})

    assert listado.status_code == 403
    assert listado.json()["detail"] == "Tu cuenta todavía no fue aprobada por un administrador."
    assert comentario.status_code == 403


@pytest.mark.parametrize("estado", SIN_APROBAR)
def test_admin_sin_aprobar_no_usa_funciones_de_admin(client, sesion, estado):
    admin = sesion(TipoUsuario.ADMINISTRADOR, estado)

    assert client.get("/auth/pendientes").status_code == 403
    # Ni se puede aprobar a sí mismo.
    assert client.post(f"/auth/aprobar/{admin.id}").status_code == 403
    assert admin.estado == estado


def test_contratista_sin_aprobar_no_usa_el_portal(client, sesion):
    sesion(TipoUsuario.CONTRATISTA, EstadoUsuario.PENDIENTE_APROBACION)

    assert client.get("/contratistas/mis-solicitudes").status_code == 403
    assert client.get("/contratistas/mis-presupuestos").status_code == 403


@pytest.mark.parametrize(
    "tipo", [TipoUsuario.ADMINISTRADOR, TipoUsuario.INSPECTOR, TipoUsuario.CONTRATISTA]
)
def test_cuenta_rechazada_con_sesion_abierta_queda_afuera(client, sesion, tipo):
    sesion(tipo, EstadoUsuario.RECHAZADO)

    respuesta = client.get("/reclamos")

    assert respuesta.status_code == 403
    assert "rechazada" in respuesta.json()["detail"]


def test_sin_aprobar_igual_ve_su_perfil_y_cierra_sesion(client, sesion):
    """La app necesita /auth/me para mostrarle la pantalla de pendiente."""
    sesion(TipoUsuario.INSPECTOR, EstadoUsuario.PENDIENTE_APROBACION)

    assert client.get("/auth/me").json()["estado"] == "PENDIENTE_APROBACION"
    assert client.post("/auth/logout").status_code == 200


def test_una_cuenta_aprobada_entra_normal(client, sesion, crear_reclamo):
    crear_reclamo()
    sesion(TipoUsuario.ADMINISTRADOR, EstadoUsuario.APROBADO)

    assert client.get("/reclamos").status_code == 200
    assert client.get("/auth/pendientes").status_code == 200


# --- Escalada a admin sin aprobación ---------------------------------------------------


def test_registrarse_como_admin_y_usar_el_token_del_email_no_da_acceso(client):
    """Registro como ADMINISTRADOR + el token del link de confirmación como cookie."""
    from unittest.mock import patch

    app.dependency_overrides.pop(get_current_admin, None)
    with patch("api.auth.enviar_confirmacion", return_value=True) as enviar:
        client.post(
            "/auth/register",
            json={
                "nombre": "Intruso",
                "email": "intruso@ejemplo.com",
                "password": "Clave123!",
                "telefono": "1155556666",
                "direccion": "Calle Falsa 123",
                "tipo": "ADMINISTRADOR",
            },
        )
    token_del_email = enviar.call_args.args[1]
    client.cookies.set(COOKIE_NAME, token_del_email)

    assert client.get("/dashboard/resumen").status_code == 401
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("tipo_token", ["confirmacion", "restablecer_password"])
def test_los_tokens_de_los_emails_no_valen_como_sesion(client, sesion, tipo_token):
    """Ni con la cuenta aprobada: el link de un email no es una sesión."""
    admin = sesion(TipoUsuario.ADMINISTRADOR, EstadoUsuario.APROBADO)
    client.cookies.set(
        COOKIE_NAME, create_access_token({"sub": str(admin.id), "tipo": tipo_token})
    )

    assert client.get("/reclamos").status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_las_sesiones_abiertas_antes_del_cambio_siguen_valiendo(client, sesion):
    """Tokens de sesión sin el campo `tipo` (emitidos antes): se aceptan hasta que vencen."""
    admin = sesion(TipoUsuario.ADMINISTRADOR, EstadoUsuario.APROBADO)
    client.cookies.set(COOKIE_NAME, create_access_token({"sub": str(admin.id)}))

    assert client.get("/reclamos").status_code == 200


def _perfil(tipo="ADMINISTRADOR"):
    return {"telefono": "1155556666", "direccion": "Calle Falsa 123", "tipo": tipo}


def test_completar_perfil_ajeno_no_se_puede(client, sesion, db):
    victima = Usuario(
        nombre="Víctima",
        email="victima@ejemplo.com",
        password_hash="",
        email_confirmado=True,
        estado=EstadoUsuario.PENDIENTE_PERFIL,
    )
    db.add(victima)
    db.flush()

    # Sin sesión.
    app.dependency_overrides.pop(get_current_admin, None)
    assert client.post(f"/auth/completar-perfil/{victima.id}", json=_perfil()).status_code == 401
    # Con la sesión de otro.
    sesion(TipoUsuario.INSPECTOR, EstadoUsuario.PENDIENTE_PERFIL)
    respuesta = client.post(f"/auth/completar-perfil/{victima.id}", json=_perfil())

    assert respuesta.status_code == 403
    assert victima.tipo is None and victima.estado == EstadoUsuario.PENDIENTE_PERFIL


def test_completar_el_perfil_propio_queda_pendiente_de_aprobacion(client, sesion):
    usuario = sesion(TipoUsuario.INSPECTOR, EstadoUsuario.PENDIENTE_PERFIL)

    respuesta = client.post(f"/auth/completar-perfil/{usuario.id}", json=_perfil())

    assert respuesta.status_code == 200
    assert usuario.estado == EstadoUsuario.PENDIENTE_APROBACION
    # Eligió ADMINISTRADOR, pero hasta que lo aprueben no usa nada de admin.
    assert client.get("/dashboard/resumen").status_code == 403
