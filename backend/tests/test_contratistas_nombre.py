"""Nombre de la empresa: el mismo mínimo (3, sin contar espacios) por todos los caminos, y
un contratista viejo que no lo cumpla no rompe los listados."""

from unittest.mock import patch

from models.contratista import Contratista
from models.usuario import TipoUsuario

DATOS = {"telefono": "1122334455", "direccion": "Calle 123", "especialidad": "Gas"}


def test_desde_la_web_no_se_crea_con_menos_de_3_caracteres_aunque_tenga_espacios(client):
    respuesta = client.post("/contratistas", json={**DATOS, "nombre_empresa": "  AB  "})

    assert respuesta.status_code == 422
    assert "al menos 3 caracteres" in respuesta.json()["detail"][0]["msg"]


def test_se_guarda_sin_espacios_de_mas(client):
    respuesta = client.post("/contratistas", json={**DATOS, "nombre_empresa": "  ABC Obras  "})

    assert respuesta.status_code == 201
    assert respuesta.json()["nombre_empresa"] == "ABC Obras"


def test_un_contratista_viejo_con_nombre_corto_no_rompe_el_listado(client, db):
    """Antes uno así (ej. aprobado desde el registro, que pedía 2) hacía fallar con 500
    todas las pantallas que listan contratistas."""
    db.add(Contratista(nombre_empresa="AB", **DATOS))
    db.flush()

    respuesta = client.get("/contratistas")

    assert respuesta.status_code == 200
    assert "AB" in [c["nombre_empresa"] for c in respuesta.json()]


def test_el_registro_como_contratista_pide_el_mismo_minimo(client):
    with patch("api.auth.enviar_confirmacion", return_value=True):
        respuesta = client.post(
            "/auth/register",
            json={
                "nombre": "Juan",
                "email": "juan-obras@ejemplo.com",
                "password": "Clave123!",
                "telefono": "1155556666",
                "direccion": "Calle Falsa 123",
                "tipo": "CONTRATISTA",
                "nombre_empresa": "AB",
                "especialidad": "Gas",
            },
        )

    assert respuesta.status_code == 422
    assert "al menos 3 caracteres" in respuesta.json()["detail"][0]["msg"]


def test_mi_perfil_de_contratista_pide_el_mismo_minimo(client, loguear):
    loguear(TipoUsuario.CONTRATISTA)

    respuesta = client.put(
        "/auth/me",
        json={
            "nombre": "Juan",
            "telefono": "1155556666",
            "direccion": "Calle Falsa 123",
            "nombre_empresa": "AB",
            "especialidad": "Gas",
        },
    )

    assert respuesta.status_code == 422
    assert "al menos 3 caracteres" in respuesta.json()["detail"]
