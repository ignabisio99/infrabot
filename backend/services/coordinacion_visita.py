"""Coordinación de la visita de trabajo entre contratista y creador del reclamo.

Flujo (todo por WhatsApp):
1. Se aprueba un presupuesto -> iniciar_coordinacion(): se crea la Visita y se le pide
   disponibilidad al contratista.
2. El contratista responde con una o varias franjas (texto libre, una por mensaje o
   separadas por líneas) y escribe "listo".
3. El bot le manda las opciones al creador del reclamo, numeradas.
4. El creador elige un número. El bot confirma la visita a ambos.
5. Un scheduler (ver services/recordatorios.py) avisa el día antes y el mismo día.

Los estados conversacionales viven en whatsapp_handler (_conversaciones). Acá está la
lógica de negocio y el envío de mensajes.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.contratista import Contratista
from models.reclamo import EstadoReclamo, Reclamo
from models.visita import EstadoVisita, Visita


def _enviar(to: str, body: str) -> None:
    """Envía un WhatsApp sin romper el flujo si falla."""
    from core.whatsapp_client import enviar_mensaje

    try:
        enviar_mensaje(to, body)
    except Exception as e:  # noqa: BLE001
        print(f"[VISITA] No se pudo enviar mensaje a {to}: {e}")


def iniciar_coordinacion(db: Session, reclamo: Reclamo, contratista: Contratista) -> Visita | None:
    """Crea la visita y le pide disponibilidad al contratista.

    Devuelve la Visita creada, o None si falta el contacto del contratista.
    Deja al contratista en estado conversacional 'visita_disponibilidad'.
    """
    if not contratista or not contratista.telefono:
        return None

    visita = Visita(
        reclamo_id=reclamo.id,
        contratista_id=contratista.id,
        estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
    )
    db.add(visita)
    db.flush()  # obtiene visita.id sin cerrar la transacción (el endpoint hace el commit)

    # El reclamo pasa a PENDIENTE_COORDINACION: se está negociando el horario de la visita.
    from models.historial_estado_reclamo import OrigenCambioEstado
    from models.reclamo import EstadoReclamo
    from services import estados_reclamo

    if reclamo.estado == EstadoReclamo.APROBADO:
        try:
            estados_reclamo.cambiar_estado(
                db,
                reclamo,
                EstadoReclamo.PENDIENTE_COORDINACION,
                motivo="Se solicitó disponibilidad al contratista para coordinar la visita",
                origen=OrigenCambioEstado.AUTOMATICO,
            )
        except estados_reclamo.TransicionInvalida as e:
            print(f"[VISITA] No se pudo pasar el reclamo a PENDIENTE_COORDINACION: {e}")

    # Import local para evitar ciclo (handler importa este módulo indirectamente).
    from core.whatsapp_handler import registrar_estado_conversacion

    registrar_estado_conversacion(
        contratista.telefono,
        {"paso": "visita_disponibilidad", "visita_id": visita.id},
    )

    _enviar(
        contratista.telefono,
        f"🎉 *¡Tu presupuesto para el reclamo #{reclamo.id} fue aprobado!*\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n\n"
        "Para coordinar la visita de trabajo, indicanos tu disponibilidad horaria.\n\n"
        "📅 *Importante:* enviá cada opción en el formato *DD/MM HH:MM* "
        "(día/mes y hora). Por ejemplo:\n"
        "_12/08 10:00_\n"
        "_13/08 15:30_\n\n"
        "Podés mandarlas todas juntas separadas por coma, o una por mensaje.\n"
        "Respetar este formato nos permite enviarte los recordatorios automáticos.\n\n"
        "Cuando termines de cargar tus opciones, escribí *listo*.",
    )
    return visita


def _separar_opciones(texto: str) -> list[str]:
    """Divide un texto en varias opciones (por saltos de línea o comas)."""
    import re

    partes = re.split(r"[\n,]+", texto)
    return [p.strip() for p in partes if p.strip()]


def _mismo_numero(a: str, b: str) -> bool:
    """Compara dos teléfonos ignorando prefijos/formato (usa los últimos 8 dígitos)."""
    import re

    da = re.sub(r"\D", "", a or "")
    db_ = re.sub(r"\D", "", b or "")
    if not da or not db_:
        return False
    return da[-8:] == db_[-8:]


def estado_conversacion_pendiente(db: Session, telefono: str) -> dict | None:
    """Reconstruye el estado conversacional de visita a partir de la base de datos.

    Sirve para no perder el flujo si el backend se reinicia (el estado en memoria se
    borra, pero la Visita sigue en la DB). Devuelve el dict de estado o None.
    """
    # ¿Es un contratista con una visita esperando su disponibilidad?
    visitas_disp = (
        db.query(Visita)
        .filter(Visita.estado == EstadoVisita.ESPERANDO_DISPONIBILIDAD)
        .order_by(Visita.id.desc())
        .all()
    )
    for visita in visitas_disp:
        reclamo = db.get(Reclamo, visita.reclamo_id)
        if reclamo and reclamo.estado == EstadoReclamo.EN_EJECUCION:
            continue
        contratista = db.get(Contratista, visita.contratista_id)
        if contratista and _mismo_numero(contratista.telefono, telefono):
            return {"paso": "visita_disponibilidad", "visita_id": visita.id}

    # ¿Es el creador de un reclamo con una visita esperando que elija horario?
    visitas_elec = (
        db.query(Visita)
        .filter(Visita.estado == EstadoVisita.ESPERANDO_ELECCION)
        .order_by(Visita.id.desc())
        .all()
    )
    for visita in visitas_elec:
        reclamo = db.get(Reclamo, visita.reclamo_id)
        if reclamo and _mismo_numero(reclamo.telefono_creador, telefono):
            return {"paso": "visita_eleccion", "visita_id": visita.id}

    return None


def formato_valido(texto: str) -> bool:
    """True si el texto tiene al menos una opción y todas son parseables (DD/MM HH:MM)."""
    opciones = _separar_opciones(texto)
    if not opciones:
        return False
    return all(_parsear_fecha(op) is not None for op in opciones)


def agregar_disponibilidad(db: Session, visita: Visita, texto: str) -> int:
    """Suma una o varias franjas de disponibilidad. Devuelve cuántas agregó.

    Acepta varias opciones en un mismo mensaje separadas por coma o salto de línea,
    o una por mensaje. Guarda una por línea.
    """
    opciones = _separar_opciones(texto)
    actuales = visita.disponibilidades or ""
    for op in opciones:
        prefijo = "\n" if actuales else ""
        actuales = actuales + prefijo + op
    visita.disponibilidades = actuales
    db.commit()
    return len(opciones)


def _opciones_lista(visita: Visita) -> list[str]:
    if not visita.disponibilidades:
        return []
    return [linea.strip() for linea in visita.disponibilidades.splitlines() if linea.strip()]


def finalizar_disponibilidad(db: Session, visita: Visita) -> bool:
    """El contratista terminó de cargar disponibilidad. Se la manda al creador.

    Devuelve True si había al menos una opción y se pasó al creador; False si no.
    Deja al creador en estado conversacional 'visita_eleccion'.
    """
    opciones = _opciones_lista(visita)
    if not opciones:
        return False

    reclamo = db.get(Reclamo, visita.reclamo_id)
    if reclamo is None or not reclamo.telefono_creador:
        return False

    visita.estado = EstadoVisita.ESPERANDO_ELECCION
    db.commit()

    from core.whatsapp_handler import registrar_estado_conversacion

    registrar_estado_conversacion(
        reclamo.telefono_creador,
        {"paso": "visita_eleccion", "visita_id": visita.id},
    )

    lineas = "\n".join(f"{i + 1}. {op}" for i, op in enumerate(opciones))
    contratista = db.get(Contratista, visita.contratista_id)
    nombre = contratista.nombre_empresa if contratista else "el contratista"
    _enviar(
        reclamo.telefono_creador,
        f"🗓️ *Coordinación de visita — Reclamo #{reclamo.id}*\n\n"
        f"{nombre} propuso estos horarios para hacer la visita de trabajo:\n\n"
        f"{lineas}\n\n"
        "Respondé con el *número* de la opción que te quede mejor (ej: *1*).",
    )
    return True


def confirmar_eleccion(db: Session, visita: Visita, indice: int) -> str | None:
    """El creador eligió una opción (1-based). Confirma la visita a ambos.

    Devuelve el texto del horario confirmado, o None si el índice es inválido.
    """
    opciones = _opciones_lista(visita)
    if indice < 1 or indice > len(opciones):
        return None

    elegido = opciones[indice - 1]
    visita.horario_confirmado = elegido
    visita.estado = EstadoVisita.CONFIRMADA
    # Intentar parsear una fecha para los recordatorios (mejor esfuerzo).
    visita.fecha_visita = _parsear_fecha(elegido)

    reclamo = db.get(Reclamo, visita.reclamo_id)
    contratista = db.get(Contratista, visita.contratista_id)

    # Con la visita agendada, el reclamo pasa a VISITA_COORDINADA (todavía no se ejecuta).
    from models.historial_estado_reclamo import OrigenCambioEstado
    from models.reclamo import EstadoReclamo
    from services import estados_reclamo

    if reclamo and reclamo.estado == EstadoReclamo.PENDIENTE_COORDINACION:
        try:
            estados_reclamo.cambiar_estado(
                db,
                reclamo,
                EstadoReclamo.VISITA_COORDINADA,
                motivo=f"Visita de trabajo coordinada para: {elegido}",
                origen=OrigenCambioEstado.AUTOMATICO,
            )
        except estados_reclamo.TransicionInvalida as e:
            print(f"[VISITA] No se pudo pasar el reclamo a VISITA_COORDINADA: {e}")

    db.commit()

    # Avisar al contratista
    if contratista and contratista.telefono:
        _enviar(
            contratista.telefono,
            f"✅ *Visita confirmada — Reclamo #{reclamo.id}*\n\n"
            f"🏫 Escuela: {reclamo.nombre_escuela}\n"
            f"📍 Ubicación: {reclamo.ubicacion}\n"
            f"🗓️ Horario: {elegido}\n\n"
            "Te vamos a recordar la visita el día anterior y el mismo día.",
        )

    # Avisar al creador
    if reclamo and reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            f"✅ *Visita confirmada — Reclamo #{reclamo.id}*\n\n"
            f"🗓️ Horario: {elegido}\n\n"
            "El contratista fue notificado. Te vamos a recordar la visita el día "
            "anterior y el mismo día.",
        )

    return elegido


def _parsear_fecha(texto: str) -> datetime | None:
    """Intenta extraer una fecha/hora de un texto libre (dd/mm y HH:MM).

    Es best-effort: si no puede, devuelve None y no habrá recordatorios automáticos
    (la visita queda confirmada igual, solo sin aviso programado).
    """
    import re

    # Buscar dd/mm o dd/mm/aaaa
    m_fecha = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", texto)
    if not m_fecha:
        return None

    # Hora: tolera "16:00", "16.00", "16hs", "16 hs" o solo "16".
    # Se busca después de la fecha para no confundir con el día/mes.
    resto = texto[m_fecha.end():]
    m_hora = re.search(r"(\d{1,2})(?:[:.]?(\d{2}))?\s*(?:hs?|h)?", resto)

    dia = int(m_fecha.group(1))
    mes = int(m_fecha.group(2))
    anio_txt = m_fecha.group(3)
    ahora = datetime.now(timezone.utc)
    if anio_txt:
        anio = int(anio_txt) + (2000 if len(anio_txt) == 2 else 0)
    else:
        anio = ahora.year

    if m_hora and m_hora.group(1):
        hora = int(m_hora.group(1))
        minuto = int(m_hora.group(2)) if m_hora.group(2) else 0
    else:
        hora, minuto = 9, 0

    try:
        # Se guarda en UTC-3 (Argentina) convertido a UTC para comparar con utcnow.
        from datetime import timedelta

        art = timezone(timedelta(hours=-3))
        fecha_local = datetime(anio, mes, dia, hora, minuto, tzinfo=art)
        return fecha_local.astimezone(timezone.utc)
    except ValueError:
        return None
