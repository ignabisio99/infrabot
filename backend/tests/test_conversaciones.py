from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from core.dependencies import get_current_admin
from core.storage import UPLOADS_DIR
from core.whatsapp_handler import procesar_mensaje, reiniciar_conversacion
from main import app
from models.conversacion import Conversacion, EstadoConversacion
from models.mensaje_conversacion import AutorMensaje, MensajeConversacion, TipoMensaje
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from services import conversaciones as convs
from services.configuracion_atencion import obtener_o_crear as obtener_atencion

UTC = timezone.utc
ORIGEN = "sim5491199990000"


@pytest.fixture(autouse=True)
def horario_siempre_abierto(db):
    fila = obtener_atencion(db)
    fila.dias = [0, 1, 2, 3, 4, 5, 6]
    fila.hora_desde = "00:00"
    fila.hora_hasta = "23:59"
    fila.inactividad_usuario_min = 60
    db.flush()


def _admin_persistido(db, nombre="Admin Chats", email="admin-chats@test.local"):
    admin = Usuario(
        nombre=nombre,
        email=email,
        password_hash="x",
        tipo=TipoUsuario.ADMINISTRADOR,
        estado=EstadoUsuario.APROBADO,
    )
    db.add(admin)
    db.flush()
    app.dependency_overrides[get_current_admin] = lambda: admin
    return admin


def test_menu_incluye_boton_hablar_con_operador(db):
    respuesta = procesar_mensaje(db, "ayuda", usuario=ORIGEN)
    assert isinstance(respuesta, dict)
    ids = [b["id"] for b in respuesta.get("botones") or []]
    assert "operador" in ids
    assert any("operador" in (b.get("title") or "").lower() for b in respuesta["botones"])

    pedido = procesar_mensaje(db, "operador", usuario=ORIGEN)
    assert "operador" in str(pedido).lower()
    assert convs.activa(db, ORIGEN) is not None


def test_operador_en_una_frase_no_cancela_el_alta(db):
    reiniciar_conversacion(ORIGEN)
    procesar_mensaje(db, "nuevo", usuario=ORIGEN)

    respuesta = procesar_mensaje(db, "Jardín del operador 12", usuario=ORIGEN)

    assert convs.activa(db, ORIGEN) is None
    cuerpo = respuesta["body"] if isinstance(respuesta, dict) else str(respuesta)
    assert "pasando con un operador" not in cuerpo.lower()


def test_operador_solo_sigue_pasando_a_una_persona_durante_el_alta(db):
    reiniciar_conversacion(ORIGEN)
    procesar_mensaje(db, "nuevo", usuario=ORIGEN)

    respuesta = procesar_mensaje(db, "operador", usuario=ORIGEN)

    cuerpo = respuesta["body"] if isinstance(respuesta, dict) else str(respuesta)
    assert "pasando con un operador" in cuerpo.lower()
    assert convs.activa(db, ORIGEN) is not None


def test_pedir_hablar_con_un_humano_pasa_a_espera(db):
    respuesta = procesar_mensaje(db, "quiero hablar con un humano", usuario=ORIGEN)
    cuerpo = respuesta["body"] if isinstance(respuesta, dict) else respuesta
    assert "operador" in cuerpo.lower()
    conv = convs.activa(db, ORIGEN)
    assert conv is not None
    assert conv.estado.value == "ESPERANDO_OPERADOR"


def test_usuario_cancela_espera_y_vuelve_al_bot(db):
    procesar_mensaje(db, "operador", usuario=ORIGEN)
    assert convs.activa(db, ORIGEN) is not None

    respuesta = procesar_mensaje(db, "cancelar", usuario=ORIGEN)
    assert isinstance(respuesta, dict)
    assert "volviste" in respuesta["body"].lower()
    assert convs.activa(db, ORIGEN) is None

    otro = f"{ORIGEN}x"
    procesar_mensaje(db, "operador", usuario=otro)
    otra = procesar_mensaje(db, "volver_al_bot", usuario=otro)
    assert convs.activa(db, otro) is None
    assert "volviste" in (otra["body"] if isinstance(otra, dict) else str(otra)).lower()


def test_segundo_tomar_devuelve_409(client, db):
    _admin_persistido(db)
    convs.solicitar(db, ORIGEN)

    bandeja = client.get("/conversaciones/bandeja").json()
    assert len(bandeja["en_espera"]) == 1
    conv_id = bandeja["en_espera"][0]["id"]

    primero = client.post(f"/conversaciones/{conv_id}/tomar")
    assert primero.status_code == 200

    segundo = client.post(f"/conversaciones/{conv_id}/tomar")
    assert segundo.status_code == 409


def test_liberar_no_vuelve_a_espera(client, db):
    _admin_persistido(db, email="admin-liberar@test.local")
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")

    respuesta = client.post(f"/conversaciones/{conv_id}/liberar")
    assert respuesta.status_code == 200

    bandeja = client.get("/conversaciones/bandeja").json()
    assert bandeja["en_espera"] == []
    assert bandeja["mias"] == []
    assert convs.activa(db, ORIGEN) is None
    avisos = [
        m.texto
        for m in convs.mensajes_de_telefono(db, ORIGEN)
        if m.autor.value == "BOT" and m.texto == convs.AVISO_FIN_ATENCION
    ]
    assert avisos == [convs.AVISO_FIN_ATENCION]


def test_con_operador_el_bot_no_responde_y_el_mensaje_queda(client, db):
    _admin_persistido(db)
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")

    convs.registrar_entrante(db, ORIGEN, texto="hola operador")
    respuesta = procesar_mensaje(db, "hola operador", usuario=ORIGEN)

    assert respuesta == ""
    guardado = (
        db.query(MensajeConversacion)
        .filter(MensajeConversacion.telefono == ORIGEN, MensajeConversacion.texto == "hola operador")
        .first()
    )
    assert guardado is not None
    assert guardado.autor is AutorMensaje.USUARIO
    item = next(c for c in client.get("/conversaciones/bandeja").json()["mias"] if c["id"] == conv_id)
    assert item["ultimo_autor"] == "USUARIO"
    assert item["ultimo_id"] == guardado.id


def test_enviar_operador_queda_en_el_chat_y_en_el_sim(client, db):
    admin = _admin_persistido(db, email="admin-envio@test.local")
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")

    respuesta = client.post(
        f"/conversaciones/{conv_id}/mensajes", json={"texto": "Hola, qué pasó my brother?"}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["autor"] == "OPERADOR"
    assert cuerpo["texto"] == "Hola, qué pasó my brother?"
    assert cuerpo["operador_id"] == admin.id

    historial = client.get(f"/conversaciones/{conv_id}/mensajes").json()
    textos = [m["texto"] for m in historial]
    assert "Hola, qué pasó my brother?" in textos

    sim = client.get("/whatsapp/simular/mensajes", params={"origen": ORIGEN}).json()
    assert [m["texto"] for m in sim] == ["Hola, qué pasó my brother?"]

    sin_prefijo = ORIGEN[3:] if ORIGEN.lower().startswith("sim") else ORIGEN
    sim_alias = client.get("/whatsapp/simular/mensajes", params={"origen": sin_prefijo}).json()
    assert [m["texto"] for m in sim_alias] == ["Hola, qué pasó my brother?"]


def test_enviar_sin_ser_asignado_falla(client, db):
    _admin_persistido(db)
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")

    otro = Usuario(
        nombre="Otro",
        email="otro-admin@test.local",
        password_hash="x",
        tipo=TipoUsuario.ADMINISTRADOR,
        estado=EstadoUsuario.APROBADO,
    )
    db.add(otro)
    db.flush()
    app.dependency_overrides[get_current_admin] = lambda: otro

    respuesta = client.post(f"/conversaciones/{conv_id}/mensajes", json={"texto": "Hola"})
    assert respuesta.status_code == 403


def test_enviar_con_ventana_vencida_falla(client, db):
    _admin_persistido(db)
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")

    conv = db.get(Conversacion, conv_id)
    conv.ultimo_mensaje_usuario = datetime.now(UTC) - timedelta(hours=25)
    db.flush()

    respuesta = client.post(f"/conversaciones/{conv_id}/mensajes", json={"texto": "Hola"})
    assert respuesta.status_code == 400


def test_limpiar_media_vencida_borra_solo_lo_vencido(db):
    carpeta = UPLOADS_DIR / "conversaciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    vencido = carpeta / "vencido.bin"
    vigente = carpeta / "vigente.bin"
    vencido.write_bytes(b"x")
    vigente.write_bytes(b"y")

    ahora = datetime.now(UTC)
    viejo = MensajeConversacion(
        telefono=ORIGEN,
        autor=AutorMensaje.USUARIO,
        tipo=TipoMensaje.IMAGEN,
        media_url="/uploads/conversaciones/vencido.bin",
        media_expira_en=ahora - timedelta(days=1),
        media_eliminada=False,
    )
    nuevo = MensajeConversacion(
        telefono=ORIGEN,
        autor=AutorMensaje.USUARIO,
        tipo=TipoMensaje.IMAGEN,
        media_url="/uploads/conversaciones/vigente.bin",
        media_expira_en=ahora + timedelta(days=7),
        media_eliminada=False,
    )
    db.add_all([viejo, nuevo])
    db.flush()

    borrados = convs.limpiar_media_vencida(db)

    assert borrados == 1
    assert viejo.media_eliminada is True
    assert nuevo.media_eliminada is False
    assert not vencido.exists()
    assert vigente.exists()
    vigente.unlink()


def test_fuera_de_horario_no_crea_conversacion(monkeypatch, db):
    fila = obtener_atencion(db)
    fila.mensaje_fuera_horario = "Cerrado ahora, volvé mañana."
    db.flush()
    monkeypatch.setattr(
        "services.configuracion_atencion.dentro_de_atencion",
        lambda _db, ahora=None: False,
    )

    respuesta = procesar_mensaje(db, "operador", usuario=ORIGEN)
    cuerpo = respuesta["body"] if isinstance(respuesta, dict) else respuesta
    assert cuerpo.startswith("Cerrado ahora, volvé mañana.")
    assert [b["id"] for b in respuesta["botones"]] == ["nuevo", "buscar_reclamo", "operador"]
    assert convs.activa(db, ORIGEN) is None
    assert db.query(Conversacion).filter(Conversacion.telefono == ORIGEN).count() == 0


def test_fuera_de_horario_no_sigue_el_paso_del_alta(monkeypatch, db):
    from core.whatsapp_handler import _conversaciones

    reiniciar_conversacion(ORIGEN)
    procesar_mensaje(db, "nuevo", usuario=ORIGEN)
    assert _conversaciones[ORIGEN]["paso"] == "escuela"
    monkeypatch.setattr(
        "services.configuracion_atencion.dentro_de_atencion",
        lambda _db, ahora=None: False,
    )

    procesar_mensaje(db, "operador", usuario=ORIGEN)
    assert ORIGEN not in _conversaciones

    siguiente = procesar_mensaje(db, "hola", usuario=ORIGEN)
    cuerpo = siguiente["body"] if isinstance(siguiente, dict) else str(siguiente)
    assert "No entendí" not in cuerpo
    assert "Paso 2" not in cuerpo
    assert _conversaciones.get(ORIGEN, {}).get("paso") != "ubicacion"
    assert any(b["id"] == "nuevo" for b in (siguiente.get("botones") or []))


def test_tomar_deja_el_nombre_del_operador_en_el_sistema(client, db):
    admin = _admin_persistido(db, nombre="Laura Pérez", email="laura-tomo@test.local")
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    assert client.post(f"/conversaciones/{conv_id}/tomar").status_code == 200
    textos = [m["texto"] for m in client.get(f"/conversaciones/{conv_id}/mensajes").json()]
    assert any("Laura Pérez tomó la conversación." in t for t in textos)
    assert admin.nombre == "Laura Pérez"


def test_historial_unifica_el_mismo_telefono(client, db):
    _admin_persistido(db, email="admin-unifica@test.local")
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")
    client.post(f"/conversaciones/{conv_id}/cerrar")
    convs.solicitar(db, ORIGEN)
    segundo_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{segundo_id}/tomar")
    client.post(f"/conversaciones/{segundo_id}/cerrar")

    historial = client.get("/conversaciones/historial").json()
    del_origen = [c for c in historial if c["telefono"] == ORIGEN or c["telefono"] == ORIGEN[3:]]
    assert len(del_origen) == 1
    assert del_origen[0]["id"] == segundo_id


def test_historial_incluye_al_que_transfirio(client, db):
    origen = _admin_persistido(db, email="admin-origen@test.local")
    destino = Usuario(
        nombre="Destino",
        email="admin-destino@test.local",
        password_hash="x",
        tipo=TipoUsuario.ADMINISTRADOR,
        estado=EstadoUsuario.APROBADO,
    )
    db.add(destino)
    db.flush()

    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    assert client.post(f"/conversaciones/{conv_id}/tomar").status_code == 200
    assert (
        client.post(f"/conversaciones/{conv_id}/transferir", json={"operador_id": destino.id}).status_code
        == 200
    )

    historial = client.get("/conversaciones/historial").json()
    assert any(c["id"] == conv_id for c in historial)

    app.dependency_overrides[get_current_admin] = lambda: destino
    historial_destino = client.get("/conversaciones/historial").json()
    assert not any(c["id"] == conv_id for c in historial_destino)
    assert origen.id != destino.id


def test_reabrir_ok_y_falla_por_ventana_o_activa(client, db):
    _admin_persistido(db, email="admin-reabrir@test.local")
    convs.solicitar(db, ORIGEN)
    conv_id = client.get("/conversaciones/bandeja").json()["en_espera"][0]["id"]
    client.post(f"/conversaciones/{conv_id}/tomar")
    client.post(f"/conversaciones/{conv_id}/cerrar")

    ok = client.post(f"/conversaciones/{conv_id}/reabrir")
    assert ok.status_code == 200
    assert ok.json()["estado"] == "CON_OPERADOR"

    client.post(f"/conversaciones/{conv_id}/cerrar")
    conv = db.get(Conversacion, conv_id)
    conv.ultimo_mensaje_usuario = datetime.now(UTC) - timedelta(hours=25)
    db.flush()
    vencida = client.post(f"/conversaciones/{conv_id}/reabrir")
    assert vencida.status_code == 400

    conv.ultimo_mensaje_usuario = datetime.now(UTC)
    db.flush()
    convs.solicitar(db, ORIGEN)
    conflicto = client.post(f"/conversaciones/{conv_id}/reabrir")
    assert conflicto.status_code == 409


def test_timeout_cierra_si_ultimo_es_operador(db):
    admin = _admin_persistido(db, email="admin-timeout@test.local")
    conv = convs.solicitar(db, ORIGEN)
    convs.tomar(db, conv.id, admin)
    mensaje = convs.enviar_texto_operador(db, conv.id, admin, "¿seguís ahí?")
    mensaje.fecha = datetime.now(UTC) - timedelta(minutes=90)
    db.flush()

    convs.correr_timeouts(db)
    db.refresh(conv)
    assert conv.estado == EstadoConversacion.CERRADA


def test_el_chat_del_reclamo_encuentra_el_numero_del_simulador(client, db):
    _admin_persistido(db, email="admin-clave-tel@test.local")
    convs.registrar_entrante(db, "sim123445444443", texto="se rompió un caño")
    db.commit()

    respuesta = client.get(f"/conversaciones/telefono/{quote('+54123445444443')}/historial")

    assert respuesta.status_code == 200
    assert [m["texto"] for m in respuesta.json()["mensajes"]] == ["se rompió un caño"]


def test_historial_telefono_devuelve_los_ultimos_y_pagina_hacia_atras(client, db):
    _admin_persistido(db, email="admin-pagina-chat@test.local")
    for i in range(45):
        convs.registrar_entrante(db, ORIGEN, texto=f"msg-{i}")
    db.commit()

    primera = client.get(f"/conversaciones/telefono/{ORIGEN}/historial?limit=10")
    assert primera.status_code == 200
    cuerpo = primera.json()
    assert cuerpo["hay_mas"] is True
    textos = [m["texto"] for m in cuerpo["mensajes"]]
    assert textos == [f"msg-{i}" for i in range(35, 45)]

    min_id = cuerpo["mensajes"][0]["id"]
    segunda = client.get(f"/conversaciones/telefono/{ORIGEN}/historial?limit=10&antes_de={min_id}")
    assert segunda.status_code == 200
    atras = segunda.json()
    assert atras["hay_mas"] is True
    assert [m["texto"] for m in atras["mensajes"]] == [f"msg-{i}" for i in range(25, 35)]


def test_timeout_no_cierra_si_ultimo_es_usuario(db):
    admin = _admin_persistido(db, email="admin-timeout-user@test.local")
    conv = convs.solicitar(db, ORIGEN)
    convs.tomar(db, conv.id, admin)
    convs.enviar_texto_operador(db, conv.id, admin, "¿seguís ahí?")
    usuario = convs.registrar_entrante(db, ORIGEN, texto="sí, acá estoy")
    usuario.fecha = datetime.now(UTC) - timedelta(hours=5)
    conv.ultimo_mensaje_usuario = usuario.fecha
    db.flush()

    convs.correr_timeouts(db)
    db.refresh(conv)
    assert conv.estado == EstadoConversacion.CON_OPERADOR
