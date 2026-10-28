"""Botón *Buscar reclamo* del menú de WhatsApp: últimas consultas y búsqueda por ID."""

from datetime import UTC, datetime
from unittest.mock import patch

from core.whatsapp_handler import _mostrar_ayuda, procesar_mensaje, reiniciar_conversacion
from models.reclamo import EstadoReclamo

TELEFONO = "5491155550001"
OTRO = "5491155550002"


def _buscar(db, texto, usuario=TELEFONO):
    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        return procesar_mensaje(db, texto, usuario=usuario)


def test_el_menu_es_siempre_nuevo_buscar_y_humano():
    for ia in (True, False):
        with patch("core.whatsapp_handler.ai_config.ai_whatsapp_enabled", return_value=ia):
            botones = _mostrar_ayuda()["botones"]
        assert [b["title"] for b in botones] == [
            "📝 Nuevo reclamo",
            "🔍 Buscar reclamo",
            "🙋 Hablar con humano",
        ]
        assert botones[0]["id"] == "nuevo"


def test_sin_consultas_muestra_los_ultimos_cargados(db, crear_reclamo):
    reiniciar_conversacion(TELEFONO)
    propio = crear_reclamo(telefono_creador=TELEFONO, nombre_escuela="Escuela Propia")
    ajeno = crear_reclamo(telefono_creador=OTRO, nombre_escuela="Escuela Ajena")

    r = _buscar(db, "buscar_reclamo")

    assert "Todavía no consultaste" in r
    assert f"#{propio.id}*" in r
    assert f"#{ajeno.id}*" not in r
    assert "ver #12" in r


def test_lista_las_ultimas_5_consultas_propias_mas_recientes_primero(db, crear_reclamo):
    reiniciar_conversacion(TELEFONO)
    reclamos = [crear_reclamo(telefono_creador=TELEFONO) for _ in range(6)]
    for r in reclamos:
        _buscar(db, f"ver #{r.id}")
    # Volver a consultar el primero lo sube al tope.
    _buscar(db, f"ver #{reclamos[0].id}")

    r = _buscar(db, "buscar_reclamo")

    assert "Tus últimas consultas" in r
    ids = [linea.split("*")[1] for linea in r.splitlines() if linea.startswith("• ")]
    esperados = [reclamos[0], reclamos[5], reclamos[4], reclamos[3], reclamos[2]]
    assert ids == [f"#{x.id}" for x in esperados]


def test_no_muestra_ni_registra_reclamos_ajenos(db, crear_reclamo):
    reiniciar_conversacion(TELEFONO)
    ajeno = crear_reclamo(telefono_creador=OTRO)

    _buscar(db, "buscar_reclamo")
    r = _buscar(db, str(ajeno.id))
    assert "No encontré un reclamo tuyo" in r

    r = _buscar(db, "buscar_reclamo")
    assert f"#{ajeno.id}*" not in r


def test_buscar_por_id_desde_el_boton_muestra_el_estado(db, crear_reclamo):
    reiniciar_conversacion(TELEFONO)
    propio = crear_reclamo(telefono_creador=TELEFONO)

    _buscar(db, "buscar_reclamo")
    r = _buscar(db, f"#{propio.id}")

    assert f"Reclamo #{propio.id}" in r
    assert "Estado:" in r


def test_estado_muestra_fecha_de_inicio_en_hora_argentina(db, crear_reclamo):
    reiniciar_conversacion(TELEFONO)
    # 02:30 UTC = 23:30 del día anterior en Argentina.
    propio = crear_reclamo(
        telefono_creador=TELEFONO, fecha_creacion=datetime(2026, 10, 10, 2, 30, tzinfo=UTC)
    )

    r = _buscar(db, f"ver #{propio.id}")

    assert "Fecha de inicio: 09/10/2026 23:30" in r
    assert "finalización" not in r


def test_reclamo_finalizado_muestra_la_fecha_en_que_termino(db, crear_reclamo, crear_historial):
    reiniciar_conversacion(TELEFONO)
    propio = crear_reclamo(
        estado=EstadoReclamo.FINALIZADO,
        telefono_creador=TELEFONO,
        fecha_creacion=datetime(2026, 10, 1, 13, 0, tzinfo=UTC),
    )
    crear_historial(propio, EstadoReclamo.FINALIZADO, datetime(2026, 10, 15, 18, 45, tzinfo=UTC))
    db.refresh(propio)

    r = _buscar(db, f"ver #{propio.id}")

    assert "Fecha de inicio: 01/10/2026 10:00" in r
    assert "Fecha de finalización: 15/10/2026 15:45" in r


def test_rechazado_muestra_fecha_de_cierre_y_desierto_no(db, crear_reclamo, crear_historial):
    reiniciar_conversacion(TELEFONO)
    rechazado = crear_reclamo(estado=EstadoReclamo.RECHAZADO, telefono_creador=TELEFONO)
    crear_historial(rechazado, EstadoReclamo.RECHAZADO, datetime(2026, 10, 5, 12, 0, tzinfo=UTC))
    desierto = crear_reclamo(estado=EstadoReclamo.DESIERTO, telefono_creador=TELEFONO)
    crear_historial(desierto, EstadoReclamo.DESIERTO, datetime(2026, 10, 5, 12, 0, tzinfo=UTC))
    db.refresh(rechazado)
    db.refresh(desierto)

    assert "Fecha de cierre: 05/10/2026 09:00" in _buscar(db, f"ver #{rechazado.id}")
    r = _buscar(db, f"ver #{desierto.id}")
    assert "cierre" not in r and "finalización" not in r
