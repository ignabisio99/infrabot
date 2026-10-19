"""CU-05 flujo proactivo por WhatsApp: inicio de obra, terminación y resolución.

El bot pregunta con botones (los IDs están en services.cu05_botones). Acá se simulan las
respuestas del contratista y de la escuela y se verifica el avance de estados.

Los envíos se mockean en core.whatsapp_client (enviar_mensaje / enviar_botones), que es lo
que importan localmente los servicios y schedulers.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.whatsapp_handler import (
    procesar_media,
    procesar_mensaje,
    registrar_estado_conversacion,
    reiniciar_conversacion,
)
from models.comentario_reclamo import ComentarioReclamo
from models.foto_reclamo import FotoReclamo
from models.historial_estado_reclamo import OrigenCambioEstado
from models.recordatorio_contratista import RecordatorioContratista
from models.reclamo import EstadoReclamo
from models.visita import EstadoVisita
from services import coordinacion_visita, cu05_botones, resolucion_escuela


# --- Pieza 1: inicio de obra ------------------------------------------------------------


def test_pregunta_inicio_se_envia_en_el_horario(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista, crear_visita
):
    from services.recordatorios import revisar_recordatorios

    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA, telefono_creador="5491199998888")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    visita = crear_visita(
        reclamo,
        fecha_visita=datetime.now(timezone.utc) - timedelta(minutes=5),
        estado=EstadoVisita.CONFIRMADA,
        contratista=contratista,
    )
    visita.horario_confirmado = "12/08 10:00"
    db.flush()

    with patch("core.whatsapp_client.enviar_botones") as botones:
        revisar_recordatorios(db)

    botones.assert_called_once()
    db.refresh(visita)
    assert visita.pregunta_inicio_enviada is not None


def test_contratista_confirma_inicio_pasa_a_ejecucion(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista, crear_visita
):
    contratista = crear_contratista()
    contratista.telefono = "5491133445566"
    reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA, telefono_creador="5491144556677")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    visita = crear_visita(
        reclamo, fecha_visita=datetime.now(timezone.utc), estado=EstadoVisita.CONFIRMADA, contratista=contratista
    )
    telefono = "5491133445566"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(
        telefono, {"paso": "cu05_inicio", "visita_id": visita.id, "reclamo_id": reclamo.id}
    )

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        r = procesar_mensaje(db, cu05_botones.INICIO_SI, usuario=telefono)

    assert "ejecución" in r.lower()
    assert "mañana" in r.lower()
    assert "terminé" in r.lower()
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION


def test_contratista_no_pudo_reprograma_visita(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista, crear_visita
):
    contratista = crear_contratista()
    contratista.telefono = "5491155667788"
    reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    visita = crear_visita(
        reclamo, fecha_visita=datetime.now(timezone.utc), estado=EstadoVisita.CONFIRMADA, contratista=contratista
    )
    telefono = "5491155667788"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(
        telefono, {"paso": "cu05_inicio", "visita_id": visita.id, "reclamo_id": reclamo.id}
    )

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        procesar_mensaje(db, cu05_botones.INICIO_NO, usuario=telefono)

    db.refresh(reclamo)
    db.refresh(visita)
    assert reclamo.estado == EstadoReclamo.PENDIENTE_COORDINACION
    assert visita.estado == EstadoVisita.ESPERANDO_DISPONIBILIDAD


# --- Pieza 2: terminación ---------------------------------------------------------------


def test_contratista_termino_consulta_a_la_escuela(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491166778899"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491100112233")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491166778899"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_termino", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones") as botones:
        r = procesar_mensaje(db, cu05_botones.TERMINO_SI, usuario=telefono)

    # Sigue EN_EJECUCION hasta que la escuela confirme, y se le preguntó a la escuela.
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.consulto_escuela is True
    botones.assert_called()  # pregunta a la escuela
    assert "escuela" in r.lower()


def test_contratista_todavia_no_pide_reporte_y_estimado(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491177889900"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491177889900"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_termino", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        r1 = procesar_mensaje(db, cu05_botones.TERMINO_NO, usuario=telefono)
        assert "porcentaje" in r1.lower()
        r2 = procesar_mensaje(db, "40%", usuario=telefono)
        assert "etapa" in r2.lower()
        r3 = procesar_mensaje(db, "Falta pintar y colocar las aberturas", usuario=telefono)
        assert "opcional" in r3.lower()
        procesar_media(db, telefono, "/uploads/avance.jpg", "image/jpeg")
        r4 = procesar_mensaje(db, "listo", usuario=telefono)
        assert "cuánto" in r4.lower()
        r5 = procesar_mensaje(db, "2 días", usuario=telefono)

    assert "anotado" in r5.lower()
    assert db.query(ComentarioReclamo).filter(
        ComentarioReclamo.reclamo_id == reclamo.id,
        ComentarioReclamo.texto.contains("Tiempo estimado restante informado: 2 días"),
    ).count() == 1
    assert db.query(FotoReclamo).filter_by(reclamo_id=reclamo.id).count() == 1
    reporte = (
        db.query(ComentarioReclamo)
        .filter(
            ComentarioReclamo.reclamo_id == reclamo.id,
            ComentarioReclamo.texto.contains("Reporte de avance"),
        )
        .one()
    )
    assert "Avance: 40%" in reporte.texto
    assert "Falta pintar y colocar las aberturas" in reporte.texto
    assert "Fotos/videos enviados: 1" in reporte.texto


def test_reporte_de_avance_valida_porcentaje_y_las_fotos_son_opcionales(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491177889911"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491177889911"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_termino", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        procesar_mensaje(db, cu05_botones.TERMINO_NO, usuario=telefono)
        assert "0 al 100" in procesar_mensaje(db, "bastante", usuario=telefono)
        assert "0 al 100" in procesar_mensaje(db, "150", usuario=telefono)
        procesar_mensaje(db, "60", usuario=telefono)
        procesar_mensaje(db, "Ya está hecha la instalación eléctrica", usuario=telefono)
        r = procesar_mensaje(db, "omitir", usuario=telefono)

    assert "cuánto" in r.lower()
    reporte = (
        db.query(ComentarioReclamo)
        .filter(
            ComentarioReclamo.reclamo_id == reclamo.id,
            ComentarioReclamo.texto.contains("Reporte de avance"),
        )
        .one()
    )
    assert "Avance: 60%" in reporte.texto
    assert "Fotos/videos enviados: 0" in reporte.texto


def test_reporte_de_avance_100_por_ciento_y_termine_cierra(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491177889922"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491100112244")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491177889922"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_termino", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        procesar_mensaje(db, cu05_botones.TERMINO_NO, usuario=telefono)
        assert "terminé" in procesar_mensaje(db, "100%", usuario=telefono)
        r = procesar_mensaje(db, "terminé", usuario=telefono)

    assert "terminado" in r.lower()
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.consulto_escuela is True


# --- Pieza 3: resolución de la escuela --------------------------------------------------


def test_escuela_confirma_resuelto_finaliza(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491177889900")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491177889900"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_resuelto", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        r = procesar_mensaje(db, cu05_botones.RESUELTO_SI, usuario=telefono)

    assert "finalizado" in r.lower()
    assert reclamo.estado == EstadoReclamo.FINALIZADO
    ultimo = reclamo.historial_estados[-1]
    assert ultimo.estado_nuevo == EstadoReclamo.FINALIZADO
    assert ultimo.origen == OrigenCambioEstado.AUTOMATICO


def test_escuela_dice_no_reactiva_seguimiento(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491166778800")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    db.add(
        RecordatorioContratista(
            reclamo_id=reclamo.id,
            ultimo_envio=datetime.now(timezone.utc),
            cantidad_envios=3,
            consulto_escuela=True,
        )
    )
    db.flush()
    telefono = "5491166778800"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "cu05_resuelto", "reclamo_id": reclamo.id})

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones"):
        procesar_mensaje(db, cu05_botones.RESUELTO_NO, usuario=telefono)

    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.consulto_escuela is False
    assert fila.cantidad_envios == 0


# --- Servicios directos (sin pasar por el handler) --------------------------------------


def test_servicio_inicio_obra_pasa_a_ejecucion(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA, telefono_creador="5491199998888")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )

    with patch("core.whatsapp_client.enviar_mensaje") as enviar:
        cambio = coordinacion_visita.registrar_inicio_obra(db, reclamo, contratista)

    assert cambio is True
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    enviar.assert_called_once()
    assert enviar.call_args.args[0] == "5491199998888"


def test_servicio_resolucion_finaliza(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491199998888")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )

    with patch("core.whatsapp_client.enviar_mensaje") as enviar:
        cambio = resolucion_escuela.registrar_resolucion(db, reclamo)

    assert cambio is True
    assert reclamo.estado == EstadoReclamo.FINALIZADO
    destinos = {llamada.args[0] for llamada in enviar.call_args_list}
    assert "5491199998888" in destinos
    assert "5491122334455" in destinos


def test_contratista_avisa_terminado_proactivamente(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    """El contratista manda 'terminé' por iniciativa propia (sin recordatorio activo)."""
    contratista = crear_contratista()
    contratista.telefono = "5491166778899"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491100112233")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491166778899"
    reiniciar_conversacion(telefono)

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones") as botones:
        r = procesar_mensaje(db, "terminé", usuario=telefono)

    assert "terminado" in r.lower()
    assert "escuela" in r.lower()
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.consulto_escuela is True
    botones.assert_called_once()
    assert botones.call_args.args[0] == "5491100112233"


def test_contratista_avisa_ya_termine_el_trabajo(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    """Variación de frase libre: 'ya terminé el trabajo'."""
    contratista = crear_contratista()
    contratista.telefono = "5491177665544"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491100223344")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491177665544"
    reiniciar_conversacion(telefono)

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones") as botones:
        r = procesar_mensaje(db, "ya terminé el trabajo", usuario=telefono)

    assert "terminado" in r.lower()
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.consulto_escuela is True
    botones.assert_called_once()


def test_contratista_repite_termine_mientras_espera_escuela(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    """Si el contratista vuelve a escribir 'terminé' mientras espera a la escuela, no re-consulta."""
    contratista = crear_contratista()
    contratista.telefono = "5491188990011"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador="5491100334455")
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491188990011"
    reiniciar_conversacion(telefono)

    with patch("core.whatsapp_client.enviar_mensaje"), patch("core.whatsapp_client.enviar_botones") as botones:
        r1 = procesar_mensaje(db, "terminé", usuario=telefono)
        assert "terminado" in r1.lower()
        assert botones.call_count == 1

        r2 = procesar_mensaje(db, "terminé", usuario=telefono)
        assert "ya tenemos registrado" in r2.lower()
        # No volvió a llamar a la escuela
        assert botones.call_count == 1

