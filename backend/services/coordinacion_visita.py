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

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from core import reloj
from core.email import enviar_reclamo_cancelado_asignado
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

    f1, f2 = ejemplo_formato_fecha()
    _enviar(
        contratista.telefono,
        f"🎉 *¡Tu presupuesto para el reclamo #{reclamo.id} fue aprobado!*\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n\n"
        "Para coordinar la visita de trabajo, indicanos tu disponibilidad horaria.\n\n"
        "📅 *Importante:* enviá cada opción en el formato *DD/MM HH:MM* "
        "o *DD/MM/AAAA HH:MM*. Por ejemplo:\n"
        f"_{f1}_\n"
        f"_{f2}_\n\n"
        "Podés mandarlas todas juntas separadas por coma, o una por mensaje.\n"
        "Respetar este formato nos permite enviarte los recordatorios automáticos.\n\n"
        "Cuando termines de cargar tus opciones, escribí *listo*.",
    )
    return visita


def cancelar_visitas(db: Session, reclamo: Reclamo) -> None:
    """Da de baja las visitas del reclamo que siguen vivas. No hace commit.

    Sin esto el scheduler de recordatorios (que sólo mira el estado de la visita)
    seguiría avisando de una visita que ya no va a ocurrir.
    """
    visitas = (
        db.query(Visita)
        .filter(Visita.reclamo_id == reclamo.id, Visita.estado != EstadoVisita.CANCELADA)
        .all()
    )
    for visita in visitas:
        visita.estado = EstadoVisita.CANCELADA


def visita_vigente(db: Session, reclamo: Reclamo) -> Visita | None:
    """La última visita del reclamo que no está cancelada, o None."""
    return (
        db.query(Visita)
        .filter(Visita.reclamo_id == reclamo.id, Visita.estado != EstadoVisita.CANCELADA)
        .order_by(Visita.id.desc())
        .first()
    )


def avisar_visita_cancelada(db: Session, visita: Visita, motivo: str | None) -> None:
    """Se canceló el reclamo: el contratista y la escuela se enteran de que no va más.

    Al contratista también por mail: si no le escribió al bot en las últimas 24 h el
    WhatsApp no le llega, y podría presentarse igual en la escuela.
    """
    reclamo = db.get(Reclamo, visita.reclamo_id)
    contratista = db.get(Contratista, visita.contratista_id)
    if reclamo is None:
        return

    escuela = reclamo.nombre_escuela or "la escuela"
    empresa = (contratista.nombre_empresa if contratista else None) or "el contratista"
    # Si la visita ya pasó, lo que se corta es el trabajo en curso, no la visita.
    horario_suspendido = (
        visita.horario_confirmado
        if visita.fecha_visita is not None and visita.fecha_visita > reloj.ahora()
        else None
    )
    linea_visita = (
        f"\n🗓️ La visita del {horario_suspendido} queda suspendida." if horario_suspendido else ""
    )
    pie = f"{linea_visita}\n\nMotivo: {motivo or '—'}"

    if contratista and contratista.telefono:
        _enviar(
            contratista.telefono,
            f"🚫 *Reclamo #{reclamo.id} — cancelado*\n\n"
            f"🏫 Escuela: {escuela}\n\n"
            f"Se canceló el reclamo, así que ya no estás asignado a este trabajo.{pie}",
        )
    if contratista:
        # Import local: api.reclamos importa este módulo.
        from api.reclamos import _email_del_contratista

        email = _email_del_contratista(db, contratista)
        if email:
            try:
                enviar_reclamo_cancelado_asignado(
                    email, reclamo.id, escuela, horario_suspendido, motivo
                )
            except Exception as e:  # noqa: BLE001
                print(f"[VISITA] No se pudo enviar mail a {email}: {e}")
    if reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            f"🚫 *Reclamo #{reclamo.id} — cancelado*\n\n"
            f"🏫 Escuela: {escuela}\n\n"
            f"Se canceló el reclamo, así que {empresa} ya no va a hacer el trabajo.{pie}",
        )


def _separar_opciones(texto: str) -> list[str]:
    """Divide un texto en varias opciones (por saltos de línea o comas)."""
    partes = re.split(r"[\n,]+", texto)
    return [p.strip() for p in partes if p.strip()]


def _mismo_numero(a: str, b: str) -> bool:
    """Compara dos teléfonos ignorando prefijos/formato (usa los últimos 8 dígitos)."""
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
        if visita.disponibilidad_pausada:
            continue
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
        if visita.eleccion_pausada:
            continue
        if reclamo and _mismo_numero(reclamo.telefono_creador, telefono):
            return {"paso": "visita_eleccion", "visita_id": visita.id}

    return None


def pausar_disponibilidad(db: Session, visita: Visita) -> None:
    """El contratista canceló la carga: se la deja en pausa hasta que la retome."""
    visita.disponibilidad_pausada = True
    db.commit()


def pausar_eleccion(db: Session, visita: Visita) -> None:
    """La escuela canceló la elección: no se la vuelve a ofrecer hasta que la retome."""
    visita.eleccion_pausada = True
    db.commit()


def _visitas_esperando_eleccion_de(db: Session, telefono: str) -> list[Visita]:
    visitas = (
        db.query(Visita)
        .filter(Visita.estado == EstadoVisita.ESPERANDO_ELECCION)
        .order_by(Visita.id.desc())
        .all()
    )
    propias = []
    for visita in visitas:
        reclamo = db.get(Reclamo, visita.reclamo_id)
        if reclamo and _mismo_numero(reclamo.telefono_creador, telefono):
            propias.append(visita)
    return propias


def elecciones_pausadas(db: Session, telefono: str) -> list[Visita]:
    return [
        visita
        for visita in _visitas_esperando_eleccion_de(db, telefono)
        if visita.eleccion_pausada
    ]


def retomar_eleccion(db: Session, telefono: str, reclamo_id: int) -> Visita | None:
    """*elegir horario <id>*: vuelve a la elección de la visita de ese reclamo."""
    for visita in _visitas_esperando_eleccion_de(db, telefono):
        if visita.reclamo_id == reclamo_id:
            visita.eleccion_pausada = False
            db.commit()
            return visita
    return None


def retomar_disponibilidad(db: Session, telefono: str, reclamo_id: int) -> Visita | None:
    """*cargar horario <id>*: vuelve a la carga de la visita de ese reclamo.

    Solo si la visita es de este contratista y sigue esperando su disponibilidad.
    """
    visitas = (
        db.query(Visita)
        .filter(
            Visita.reclamo_id == reclamo_id,
            Visita.estado == EstadoVisita.ESPERANDO_DISPONIBILIDAD,
        )
        .order_by(Visita.id.desc())
        .all()
    )
    for visita in visitas:
        contratista = db.get(Contratista, visita.contratista_id)
        if contratista and _mismo_numero(contratista.telefono, telefono):
            visita.disponibilidad_pausada = False
            db.commit()
            return visita
    return None


class FechaPasada(Exception):
    """La fecha de la visita ya pasó y no se puede coordinar."""


def ejemplo_formato_fecha() -> tuple[str, str]:
    """Ejemplos futuros en el formato que se guarda: DD/MM/AAAA HH:MM."""
    ahora_art = reloj.ahora_art()
    f1 = (ahora_art + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    f2 = (ahora_art + timedelta(days=2)).replace(hour=15, minute=30, second=0, microsecond=0)
    return reloj.formatear_art(f1), reloj.formatear_art(f2)


def formato_valido(texto: str) -> bool:
    """True si el texto tiene al menos una opción y todas son parseables (DD/MM HH:MM)."""
    opciones = _separar_opciones(texto)
    if not opciones:
        return False
    return all(_parsear_fecha(op) is not None for op in opciones)


def opciones_pasadas(texto: str) -> list[str]:
    """Devuelve las opciones cuya fecha/hora es anterior o igual al momento actual."""
    opciones = _separar_opciones(texto)
    ahora = reloj.ahora()
    pasadas = []
    for op in opciones:
        dt = _parsear_fecha(op)
        if dt is not None and dt <= ahora:
            pasadas.append(op)
    return pasadas


def es_fecha_futura(texto_opcion: str) -> bool:
    """True si la opción se puede parsear y su fecha/hora es posterior al momento actual."""
    dt = _parsear_fecha(texto_opcion)
    if dt is None:
        return False
    return dt > reloj.ahora()


def agregar_disponibilidad(db: Session, visita: Visita, texto: str) -> int:
    """Suma franjas nuevas y devuelve cuántas quedaron cargadas en total.

    No repite un horario que ya estaba. Acepta varias opciones en un mensaje
    separadas por coma o salto de línea.
    """
    cargadas = []
    for op in _opciones_lista(visita):
        canon = formatear_opcion(op) or op
        if canon not in cargadas:
            cargadas.append(canon)
    for op in _separar_opciones(texto):
        canon = formatear_opcion(op)
        if canon and canon not in cargadas:
            cargadas.append(canon)
    visita.disponibilidades = "\n".join(cargadas) or None
    db.commit()
    return len(cargadas)


def _opciones_lista(visita: Visita) -> list[str]:
    if not visita.disponibilidades:
        return []
    return [linea.strip() for linea in visita.disponibilidades.splitlines() if linea.strip()]


def finalizar_disponibilidad(db: Session, visita: Visita) -> tuple[bool, str | None]:
    """El contratista terminó de cargar disponibilidad. Se la manda al creador.

    Filtra opciones que hayan quedado en el pasado.
    Devuelve (True, None) si se mandó al creador.
    Devuelve (False, "sin_opciones") si no había opciones.
    Devuelve (False, "todas_pasadas") si todas las opciones cargadas ya vencieron.
    Devuelve (False, "sin_contacto") si falta el reclamo o teléfono del creador.
    """
    opciones = _opciones_lista(visita)
    if not opciones:
        return False, "sin_opciones"

    # Filtrar solo opciones que sigan vigentes (futuras)
    ahora = reloj.ahora()
    opciones_vigentes = []
    for op in opciones:
        dt = _parsear_fecha(op)
        if dt is None or dt <= ahora:
            continue
        canon = reloj.formatear_art(dt)
        if canon not in opciones_vigentes:
            opciones_vigentes.append(canon)

    if not opciones_vigentes:
        visita.disponibilidades = None
        db.commit()
        return False, "todas_pasadas"

    reclamo = db.get(Reclamo, visita.reclamo_id)
    if reclamo is None or not reclamo.telefono_creador:
        return False, "sin_contacto"

    # Actualizar para conservar solo las vigentes
    visita.disponibilidades = "\n".join(opciones_vigentes)
    visita.estado = EstadoVisita.ESPERANDO_ELECCION
    visita.eleccion_pausada = False
    contratista = db.get(Contratista, visita.contratista_id)
    nombre = contratista.nombre_empresa if contratista else "el contratista"
    _anotar_horarios_propuestos(db, reclamo, contratista, opciones_vigentes)
    db.commit()

    from core.whatsapp_handler import registrar_estado_conversacion

    registrar_estado_conversacion(
        reclamo.telefono_creador,
        {"paso": "visita_eleccion", "visita_id": visita.id},
    )

    lineas = "\n".join(f"{i + 1}. {op}" for i, op in enumerate(opciones_vigentes))
    _enviar(
        reclamo.telefono_creador,
        f"🗓️ *Coordinación de visita — Reclamo #{reclamo.id}*\n\n"
        f"{nombre} propuso estos horarios para hacer la visita de trabajo:\n\n"
        f"{lineas}\n\n"
        "Respondé con el *número* de la opción que te quede mejor (ej: *1*).\n"
        "Si ahora no podés elegir, escribí *cancelar*.",
    )
    return True, None


def _anotar_horarios_propuestos(
    db: Session, reclamo: Reclamo, contratista: Contratista | None, opciones: list[str]
) -> None:
    """Deja en la línea de tiempo del reclamo (bajo "Pendiente de coordinación") los
    horarios que propuso el contratista. Cuál eligió la escuela queda en el motivo del
    paso a "Visita coordinada"."""
    from models.comentario_reclamo import ComentarioReclamo

    empresa = (contratista.nombre_empresa if contratista else "Contratista").strip()
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=getattr(contratista, "usuario_id", None),
            texto=f"[WhatsApp — {empresa}]\nEl contratista propuso estos horarios para la visita:\n"
            + "\n".join(f"• {op}" for op in opciones),
        )
    )


def mensaje_visita_confirmada_creador(reclamo: Reclamo, elegido: str) -> str:
    return (
        f"✅ *Visita confirmada — Reclamo #{reclamo.id}*\n\n"
        f"🗓️ Horario: {elegido}\n\n"
        "El contratista fue notificado. Te vamos a recordar la visita el día "
        "anterior y el mismo día."
    )


def confirmar_eleccion(
    db: Session, visita: Visita, indice: int, *, avisar_creador: bool = True
) -> str | None:
    """El creador eligió una opción (1-based). Confirma la visita a ambos.

    Con `avisar_creador=False` no le manda la confirmación al creador: lo usa el handler
    cuando el creador acaba de elegir, para contestarle con un solo mensaje.
    Devuelve el texto del horario confirmado, o None si el índice es inválido.
    Lanza FechaPasada si la opción elegida ya pasó.
    """
    opciones = _opciones_lista(visita)
    if indice < 1 or indice > len(opciones):
        return None

    elegido = opciones[indice - 1]
    fecha_dt = _parsear_fecha(elegido)
    ahora = reloj.ahora()

    # Validar que no haya vencido la opción elegida
    if fecha_dt is not None and fecha_dt <= ahora:
        raise FechaPasada(f"La opción elegida ({elegido}) ya pasó.")

    horario = reloj.formatear_art(fecha_dt) if fecha_dt is not None else elegido
    visita.horario_confirmado = horario
    visita.estado = EstadoVisita.CONFIRMADA
    visita.fecha_visita = fecha_dt

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
                motivo=f"Visita de trabajo coordinada para: {horario}",
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
            f"📍 Ubicación: {reclamo.ubicacion}\n\n"
            f"🗓️ Horario: {horario}\n\n"
            "Te vamos a recordar la visita el día anterior y el mismo día.",
        )

    # Avisar al creador. El handler lo pide en False para contestarle en el mismo mensaje.
    if avisar_creador and reclamo and reclamo.telefono_creador:
        _enviar(reclamo.telefono_creador, mensaje_visita_confirmada_creador(reclamo, horario))

    return horario


def formatear_opcion(texto: str) -> str | None:
    """Pasa un horario libre al texto que se guarda y se muestra: DD/MM/AAAA HH:MM."""
    dt = _parsear_fecha(texto)
    if dt is None:
        return None
    return reloj.formatear_art(dt)


def normalizar_fechas_visitas(db: Session) -> int:
    """Reescribe horarios ya guardados al formato con año.

    Sin año, la fecha queda en el año en curso, salvo un enero cargado en diciembre,
    que es el enero siguiente. Con el año escrito eso no se reinterpreta. Si la
    visita ya tiene `fecha_visita`, ese instante manda sobre el texto.
    """
    cambiadas = 0
    for visita in db.query(Visita).all():
        cambio = False
        if visita.fecha_visita is not None and visita.horario_confirmado:
            canon = reloj.formatear_art(visita.fecha_visita)
            if visita.horario_confirmado != canon:
                visita.horario_confirmado = canon
                cambio = True
        elif visita.horario_confirmado:
            canon = formatear_opcion(visita.horario_confirmado)
            if canon and canon != visita.horario_confirmado:
                visita.horario_confirmado = canon
                cambio = True

        if visita.disponibilidades:
            lineas = []
            for op in _opciones_lista(visita):
                canon = formatear_opcion(op)
                lineas.append(canon or op)
                if canon and canon != op:
                    cambio = True
            if cambio:
                visita.disponibilidades = "\n".join(lineas)
        if cambio:
            cambiadas += 1
    if cambiadas:
        db.commit()
    return cambiadas


def _parsear_fecha(texto: str) -> datetime | None:
    """Extrae una fecha/hora (dd/mm[/aaaa] y HH:MM) en UTC.

    Sin año, usa el año en curso. Una fecha que ya pasó se queda en este año y
    quien coordina la rechaza: un día anterior no salta al año siguiente.
    La excepción es diciembre: un enero sin año es el enero que viene.
    Para cualquier otra fecha del año siguiente hay que escribir el año.
    Con año explícito se respeta, aunque sea pasado.
    """
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

    if m_hora and m_hora.group(1):
        hora = int(m_hora.group(1))
        minuto = int(m_hora.group(2)) if m_hora.group(2) else 0
    else:
        hora, minuto = 9, 0

    def _armar(anio: int) -> datetime | None:
        try:
            local = datetime(anio, mes, dia, hora, minuto, tzinfo=reloj.ART)
        except ValueError:
            return None
        return local.astimezone(timezone.utc)

    if anio_txt:
        anio = int(anio_txt) + (2000 if len(anio_txt) == 2 else 0)
        return _armar(anio)

    ahora_art = reloj.ahora().astimezone(reloj.ART)
    anio = ahora_art.year
    if ahora_art.month == 12 and mes == 1:
        anio += 1
    return _armar(anio)


# --- CU-05 paso 3: el contratista avisa por WhatsApp que arranca la obra ---------------
#
# Tras VISITA_COORDINADA el flujo se frenaba: nadie llevaba el reclamo a EN_EJECUCION.
# Acá se identifica al contratista por su teléfono (el del presupuesto del reclamo) y,
# cuando avisa que empezó, se dispara la transición VISITA_COORDINADA -> EN_EJECUCION.
# La transición ya es válida en la máquina de estados (origen AUTOMATICO), así que no
# hace falta tocar estados_reclamo.


def contratista_de_reclamo_coordinado(db: Session, telefono: str):
    """Reclamo en VISITA_COORDINADA cuyo contratista coincide con el teléfono.

    Devuelve (reclamo, contratista) o None. Identifica al contratista por el presupuesto
    aprobado, igual que avance_contratista.reclamo_en_ejecucion_de.
    """
    from services.estados_presupuesto import contratista_adjudicado

    reclamos = (
        db.query(Reclamo)
        .filter(Reclamo.estado == EstadoReclamo.VISITA_COORDINADA)
        .order_by(Reclamo.id.desc())
        .all()
    )
    for reclamo in reclamos:
        contratista = contratista_adjudicado(db, reclamo.id)
        if contratista and _mismo_numero(contratista.telefono, telefono):
            return reclamo, contratista
    return None


def coordinar_nueva_visita(
    db: Session, reclamo: Reclamo, *, detalle: str | None = None, cantidad_media: int = 0
) -> Contratista | None:
    """La escuela dijo que no quedó resuelto: EN_EJECUCION -> PENDIENTE_COORDINACION.

    Se crea una visita nueva (la anterior queda en el calendario como lo que fue) y se le
    pide disponibilidad al contratista, avisándole por qué (con lo que contó la escuela y
    cuántas fotos o videos mandó, que quedan en el reclamo). Desde ahí sigue el flujo de
    siempre: la escuela elige horario, "¿pudiste empezar?", seguimiento y "¿quedó
    resuelto?". Devuelve el contratista, o None si no hay a quién pedirle (el reclamo
    queda como estaba). No hace commit.
    """
    from core.whatsapp_handler import registrar_estado_conversacion
    from models.historial_estado_reclamo import OrigenCambioEstado
    from services import estados_reclamo

    if reclamo.estado != EstadoReclamo.EN_EJECUCION:
        return None
    anterior = (
        db.query(Visita).filter(Visita.reclamo_id == reclamo.id).order_by(Visita.id.desc()).first()
    )
    contratista = db.get(Contratista, anterior.contratista_id) if anterior else None
    if contratista is None or not contratista.telefono:
        return None

    # La visita anterior ya se hizo: que el scheduler no le vuelva a preguntar si empezó.
    if anterior.pregunta_inicio_enviada is None:
        anterior.pregunta_inicio_enviada = reloj.ahora()

    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.PENDIENTE_COORDINACION,
        motivo="La escuela indicó que el problema no quedó resuelto: se coordina una nueva visita",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    visita = Visita(
        reclamo_id=reclamo.id,
        contratista_id=contratista.id,
        estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
    )
    db.add(visita)
    db.flush()

    registrar_estado_conversacion(
        contratista.telefono,
        {"paso": "visita_disponibilidad", "visita_id": visita.id},
    )
    f1, f2 = ejemplo_formato_fecha()
    que_quedo_mal = f"📝 La escuela dice: _{detalle.strip()}_\n" if detalle else ""
    if cantidad_media:
        que_quedo_mal += f"📎 Mandó {cantidad_media} foto(s)/video(s): los ves en el reclamo.\n"
    _enviar(
        contratista.telefono,
        f"⚠️ *Reclamo #{reclamo.id} — la escuela indicó que no quedó resuelto*\n\n"
        f"🏫 {reclamo.nombre_escuela}\n"
        f"📍 {reclamo.ubicacion}\n"
        f"{que_quedo_mal}\n"
        "Coordinemos una nueva visita para terminar el trabajo. Indicá tu disponibilidad "
        f"en formato *DD/MM HH:MM* (ej: _{f1}_, _{f2}_; podés mandar varias separadas por "
        "coma).\n"
        "Cuando termines, escribí *listo*.",
    )
    return contratista


def registrar_inicio_obra(db: Session, reclamo: Reclamo, contratista) -> bool:
    """El contratista avisó que empezó: VISITA_COORDINADA -> EN_EJECUCION.

    Deja un comentario de sistema y avisa a la escuela (telefono_creador). Devuelve True
    si cambió el estado; False si el reclamo no estaba en VISITA_COORDINADA.
    """
    from models.comentario_reclamo import ComentarioReclamo
    from models.historial_estado_reclamo import OrigenCambioEstado
    from services import estados_reclamo

    if reclamo.estado != EstadoReclamo.VISITA_COORDINADA:
        return False

    empresa = (getattr(contratista, "nombre_empresa", None) or "El contratista").strip()
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.EN_EJECUCION,
        motivo="El contratista avisó por WhatsApp que inició la obra",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=getattr(contratista, "usuario_id", None),
            texto=f"[WhatsApp — {empresa}]\nEl contratista informó que comenzó el trabajo.",
        )
    )
    db.commit()

    # Avisar a la escuela que el trabajo arrancó (best-effort).
    if reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            f"🛠️ *Reclamo #{reclamo.id} — el trabajo comenzó*\n\n"
            f"🏫 {reclamo.nombre_escuela}\n"
            f"📍 {reclamo.ubicacion}\n\n"
            f"{empresa} informó que inició la obra. Cuando el problema esté resuelto, "
            "te vamos a pedir por este chat que lo confirmes.",
        )
    return True


# --- CU-05 pieza 1: preguntar al contratista si empezó, en el horario pactado ----------
#
# El scheduler de recordatorios detecta que llegó la fecha_visita y llama acá. Se pregunta
# una sola vez (marca Visita.pregunta_inicio_enviada). Si el contratista responde que no
# pudo, se reprograma la visita reutilizando el flujo de coordinación.


def _enviar_botones(to: str, body: str, botones: list[dict]) -> None:
    """Envía botones interactivos sin romper el flujo si falla."""
    from core.whatsapp_client import enviar_botones

    try:
        enviar_botones(to, body, botones)
    except Exception as e:  # noqa: BLE001
        print(f"[VISITA] No se pudieron enviar botones a {to}: {e}")


def enviar_pregunta_inicio(db: Session, visita: Visita) -> bool:
    """Pregunta al contratista si pudo empezar. Deja el estado conversacional listo.

    Devuelve True si se envió la pregunta; False si no hay a quién preguntarle.
    """
    from services import cu05_botones
    from core.whatsapp_handler import registrar_estado_conversacion

    reclamo = db.get(Reclamo, visita.reclamo_id)
    contratista = db.get(Contratista, visita.contratista_id)
    if reclamo is None or contratista is None or not contratista.telefono:
        return False

    registrar_estado_conversacion(
        contratista.telefono,
        {"paso": "cu05_inicio", "visita_id": visita.id, "reclamo_id": reclamo.id},
    )
    _enviar_botones(
        contratista.telefono,
        f"🛠️ *Reclamo #{reclamo.id} — {reclamo.nombre_escuela}*\n\n"
        f"Hoy era la visita de trabajo acordada ({visita.horario_confirmado}).\n"
        "¿Pudiste empezar el trabajo?",
        [
            {"id": cu05_botones.INICIO_SI, "title": "Sí, empecé"},
            {"id": cu05_botones.INICIO_NO, "title": "No pude"},
        ],
    )
    return True


def reprogramar_visita(db: Session, visita: Visita, *, avisar: bool = True) -> bool:
    """El contratista no pudo empezar: se vuelve a coordinar la visita.

    Reusa el flujo de disponibilidad: la visita vuelve a ESPERANDO_DISPONIBILIDAD, el
    reclamo a PENDIENTE_COORDINACION, y se le vuelve a pedir disponibilidad al contratista.
    Con `avisar=False` no manda el pedido: lo usa el handler cuando el contratista acaba
    de responder "no pude", para contestarle con un solo mensaje.
    """
    from models.historial_estado_reclamo import OrigenCambioEstado
    from services import estados_reclamo
    from core.whatsapp_handler import registrar_estado_conversacion

    reclamo = db.get(Reclamo, visita.reclamo_id)
    contratista = db.get(Contratista, visita.contratista_id)
    if reclamo is None or contratista is None:
        return False

    # Volver a dejar la visita pidiendo disponibilidad y limpiar lo coordinado.
    visita.estado = EstadoVisita.ESPERANDO_DISPONIBILIDAD
    visita.disponibilidad_pausada = False
    visita.eleccion_pausada = False
    visita.disponibilidades = None
    visita.horario_confirmado = None
    visita.fecha_visita = None
    visita.recordatorio_dia_antes_enviado = None
    visita.recordatorio_mismo_dia_enviado = None
    visita.pregunta_inicio_enviada = None

    if reclamo.estado == EstadoReclamo.VISITA_COORDINADA:
        try:
            estados_reclamo.cambiar_estado(
                db,
                reclamo,
                EstadoReclamo.PENDIENTE_COORDINACION,
                motivo="El contratista no pudo iniciar: se reprograma la visita",
                origen=OrigenCambioEstado.AUTOMATICO,
            )
        except estados_reclamo.TransicionInvalida as e:
            print(f"[VISITA] No se pudo reprogramar el reclamo #{reclamo.id}: {e}")
            return False
    db.commit()

    registrar_estado_conversacion(
        contratista.telefono,
        {"paso": "visita_disponibilidad", "visita_id": visita.id},
    )
    if avisar:
        _enviar(contratista.telefono, mensaje_reprogramacion(reclamo))
    return True


def mensaje_reprogramacion(reclamo: Reclamo) -> str:
    f1, _ = ejemplo_formato_fecha()
    return (
        f"📅 *Reprogramemos la visita del reclamo #{reclamo.id}*\n\n"
        f"🏫 {reclamo.nombre_escuela}\n"
        f"📍 {reclamo.ubicacion}\n\n"
        "Indicá tu nueva disponibilidad en formato *DD/MM HH:MM* "
        f"o *DD/MM/AAAA HH:MM* (ej: _{f1}_).\n"
        "La fecha tiene que ser posterior a la actual.\n"
        "Cuando termines, escribí *listo*."
    )
