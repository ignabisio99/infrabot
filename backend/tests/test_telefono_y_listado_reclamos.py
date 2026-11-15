"""B4: editar en la web un reclamo cargado por WhatsApp le cambiaba el teléfono (549… pasaba
a +549…) y el bot dejaba de reconocerlo. B5: un reclamo del bot con un nombre corto
rompía el listado entero, porque la respuesta volvía a correr los validadores del alta.
"""

from unittest.mock import patch

import pytest

from core.telefonos import mismo_telefono
from core.whatsapp_client import _normalizar_numero_ar
from core.whatsapp_handler import procesar_mensaje, reiniciar_conversacion
from models.usuario import TipoUsuario

DEL_BOT = "5491155550001"
OTRO = "5491155550002"


@pytest.fixture
def admin(loguear):
    return loguear(TipoUsuario.ADMINISTRADOR)


def _formulario(reclamo, **cambios):
    """Lo que manda el formulario de edición: los campos tal como los recibió."""
    return {
        "nombre_escuela": reclamo.nombre_escuela,
        "ubicacion": reclamo.ubicacion,
        "prioridad": reclamo.prioridad.value,
        "categoria": reclamo.categoria,
        "descripcion": reclamo.descripcion,
        "telefono_creador": reclamo.telefono_creador,
        **cambios,
    }


def _bot(db, texto, usuario=DEL_BOT):
    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        return procesar_mensaje(db, texto, usuario=usuario)


@pytest.mark.parametrize(
    "a, b, iguales",
    [
        ("5491122334455", "+54 9 11 2233-4455", True),
        ("sim5491122334455", "5491122334455", True),
        ("011 2233-4455", "+541122334455", True),
        ("5491122334455", "5491122334456", False),
        ("", "", False),
        (None, "5491122334455", False),
    ],
)
def test_mismo_telefono_ignora_el_formato(a, b, iguales):
    assert mismo_telefono(a, b) is iguales


def test_el_listado_no_se_rompe_con_un_reclamo_corto_del_bot(db, client, admin, crear_reclamo):
    corto = crear_reclamo(nombre_escuela="N5", alta_whatsapp=True)
    corto.descripcion = "goteo"
    db.flush()

    r = client.get("/reclamos")

    assert r.status_code == 200, r.text
    fila = next(x for x in r.json() if x["id"] == corto.id)
    assert fila["nombre_escuela"] == "N5"
    assert client.get(f"/reclamos/{corto.id}").status_code == 200


def test_la_respuesta_devuelve_el_telefono_como_esta_guardado(client, admin, crear_reclamo):
    reclamo = crear_reclamo(telefono_creador=DEL_BOT)

    assert client.get(f"/reclamos/{reclamo.id}").json()["telefono_creador"] == DEL_BOT


@pytest.mark.parametrize("enviado", [DEL_BOT, "+5491155550001", "+54 9 11 5555-0001"])
def test_editar_en_la_web_no_cambia_el_telefono_del_bot(db, client, admin, crear_reclamo, enviado):
    reclamo = crear_reclamo(telefono_creador=DEL_BOT)

    r = client.put(
        f"/reclamos/{reclamo.id}",
        json=_formulario(reclamo, telefono_creador=enviado, descripcion="Pérdida en el baño de planta baja"),
    )

    assert r.status_code == 200, r.text
    db.refresh(reclamo)
    assert reclamo.telefono_creador == DEL_BOT
    assert reclamo.descripcion == "Pérdida en el baño de planta baja"


def test_editar_con_otro_numero_lo_cambia_normalizado(db, client, admin, crear_reclamo):
    reclamo = crear_reclamo(telefono_creador=DEL_BOT)

    r = client.put(f"/reclamos/{reclamo.id}", json=_formulario(reclamo, telefono_creador="11 9999-0000"))

    assert r.status_code == 200, r.text
    db.refresh(reclamo)
    assert reclamo.telefono_creador == "+541199990000"


def test_el_bot_reconoce_un_reclamo_con_el_telefono_en_otro_formato(db, crear_reclamo):
    reiniciar_conversacion(DEL_BOT)
    reiniciar_conversacion(OTRO)
    editado = crear_reclamo(telefono_creador="+5491155550001", nombre_escuela="Escuela Editada")

    assert "No encontré" not in _bot(db, f"ver #{editado.id}")
    assert f"#{editado.id}" in _bot(db, "recientes")
    assert f"#{editado.id}*" in _bot(db, "buscar_reclamo")
    reiniciar_conversacion(DEL_BOT)

    assert "No encontré" in _bot(db, f"ver #{editado.id}", usuario=OTRO)
    assert f"#{editado.id}" not in _bot(db, "recientes", usuario=OTRO)


def test_el_envio_saca_el_9_tambien_con_mas():
    # AMBA: sin el 9 y con el 15, que es como Meta guarda al destinatario.
    assert _normalizar_numero_ar("+5491122334455") == "54111522334455"
    assert _normalizar_numero_ar("5491122334455") == "54111522334455"
    # Otras características: solo se saca el 9.
    assert _normalizar_numero_ar("5493514445566") == "543514445566"
    assert _normalizar_numero_ar("sim5491122334455") == "sim5491122334455"
