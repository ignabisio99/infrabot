from datetime import datetime, timezone

from models.comentario_reclamo import ComentarioReclamo
from models.recordatorio_contratista import RecordatorioContratista
from models.reclamo import EstadoReclamo
from services.avance_contratista import (
    estado_conversacion_avance,
    reclamo_en_ejecucion_de,
    registrar_avance_texto,
)
from core.whatsapp_handler import (
    procesar_mensaje,
    registrar_estado_conversacion,
    reiniciar_conversacion,
)


def test_reconoce_contratista_en_ejecucion(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    contratista = crear_contratista()
    contratista.telefono = "5491122334455"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista)

    hallado = reclamo_en_ejecucion_de(db, "11-2233-4455")
    assert hallado is not None
    assert hallado[0].id == reclamo.id


def test_avance_texto_queda_en_comentarios(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    contratista = crear_contratista()
    contratista.nombre_empresa = "Plomería Local"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista)

    registrar_avance_texto(db, reclamo, contratista, "Avance 40%")
    comentarios = db.query(ComentarioReclamo).filter_by(reclamo_id=reclamo.id).all()
    assert len(comentarios) == 1
    assert "Avance 40%" in comentarios[0].texto
    assert "Plomería Local" in comentarios[0].texto


def test_en_ejecucion_no_pide_fecha_de_visita(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista, crear_visita
):
    from models.visita import EstadoVisita

    contratista = crear_contratista()
    contratista.telefono = "5491199988877"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    crear_visita(reclamo, fecha_visita=None, estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD, contratista=contratista)
    telefono = "5491199988877"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "avance_ejecucion", "reclamo_id": reclamo.id})
    respuesta = procesar_mensaje(db, "Avance 40%, tablero listo", usuario=telefono)
    assert "Anoté el avance" in respuesta
    assert "DD/MM" not in respuesta


def test_whatsapp_avance_y_termine(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    contratista = crear_contratista()
    contratista.telefono = "5491100112233"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista)
    telefono = "5491100112233"
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "avance_ejecucion", "reclamo_id": reclamo.id})

    r1 = procesar_mensaje(db, "Avance 70%, ya está el caño nuevo", usuario=telefono)
    assert "Anoté el avance" in r1
    r2 = procesar_mensaje(db, "terminé", usuario=telefono)
    assert "terminado" in r2.lower()
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    textos = [c.texto for c in db.query(ComentarioReclamo).filter_by(reclamo_id=reclamo.id)]
    assert any("70%" in t for t in textos)
    assert any("terminado" in t.lower() for t in textos)

    r3 = procesar_mensaje(db, "hola", usuario=telefono)
    assert "Anoté el avance" not in r3
    n_despues = db.query(ComentarioReclamo).filter_by(reclamo_id=reclamo.id).count()
    assert n_despues == len(textos)


def test_sin_recordatorio_no_trata_todo_como_avance(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491100998877"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    telefono = "5491100998877"
    reiniciar_conversacion(telefono)
    assert estado_conversacion_avance(db, telefono) is None
    r = procesar_mensaje(db, "hola", usuario=telefono)
    assert "Anoté el avance" not in r
    assert db.query(ComentarioReclamo).filter_by(reclamo_id=reclamo.id).count() == 0


def test_reconstruye_avance_si_hay_recordatorio_pendiente(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    contratista.telefono = "5491188877666"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo, items=[(1, 100)], fecha_aprobacion=reclamo.fecha_creacion, contratista=contratista
    )
    db.add(
        RecordatorioContratista(
            reclamo_id=reclamo.id,
            ultimo_envio=datetime.now(timezone.utc),
            cantidad_envios=1,
        )
    )
    db.flush()
    telefono = "5491188877666"
    reiniciar_conversacion(telefono)
    r = procesar_mensaje(db, "Avance 20%", usuario=telefono)
    assert "Anoté el avance" in r
