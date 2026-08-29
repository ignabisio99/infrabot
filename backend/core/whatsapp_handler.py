"""Lógica conversacional del bot de WhatsApp.

Interpreta los mensajes entrantes y genera respuestas consultando
la base de datos de reclamos. Soporta un flujo de creación de
reclamos paso a paso.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session, joinedload

from models.foto_reclamo import FotoReclamo, TipoMedia
from models.reclamo import PrioridadReclamo, Reclamo

# Zona horaria UTC-3 (Argentina), para los timestamps de la info adicional.
ART = timezone(timedelta(hours=-3))

# Estado de conversación por usuario (en memoria)
# Clave: número de teléfono, Valor: dict con paso actual y datos parciales
_conversaciones: dict[str, dict] = {}

# Última vez que cada número escribió (en memoria). Sirve para saludar con el menú
# cuando vuelve después de un rato en vez de responder "no entendí".
_ultima_actividad: dict[str, datetime] = {}

# Si pasó más de este tiempo desde el último mensaje, tratamos la conversación como
# "nueva" y mostramos el saludo con botones.
UMBRAL_SALUDO = timedelta(hours=1)

# --- Rate limiting básico (anti-spam) ---
# Timestamps de los últimos mensajes por número, para detectar flood.
_historial_mensajes: dict[str, list[datetime]] = {}
# Hasta cuándo está bloqueado cada número por haber excedido el límite.
_bloqueados_hasta: dict[str, datetime] = {}

# Máximo de mensajes permitidos dentro de la ventana antes de bloquear.
RATE_LIMIT_MAX = 15
RATE_LIMIT_VENTANA = timedelta(minutes=1)
RATE_LIMIT_BLOQUEO = timedelta(minutes=5)


def _esta_bloqueado(usuario: str) -> bool:
    """True si el número está temporalmente bloqueado por flood."""
    hasta = _bloqueados_hasta.get(usuario)
    if hasta is None:
        return False
    if datetime.now(timezone.utc) >= hasta:
        # Expiró el bloqueo: limpiar y permitir de nuevo.
        del _bloqueados_hasta[usuario]
        _historial_mensajes.pop(usuario, None)
        return False
    return True


def _registrar_y_chequear_flood(usuario: str) -> bool:
    """Registra el mensaje y devuelve True si el número acaba de superar el límite.

    Cuenta los mensajes de la última ventana; si pasa el máximo, marca el bloqueo.
    """
    ahora = datetime.now(timezone.utc)
    limite = ahora - RATE_LIMIT_VENTANA

    marcas = [t for t in _historial_mensajes.get(usuario, []) if t > limite]
    marcas.append(ahora)
    _historial_mensajes[usuario] = marcas

    if len(marcas) > RATE_LIMIT_MAX:
        _bloqueados_hasta[usuario] = ahora + RATE_LIMIT_BLOQUEO
        return True
    return False


def _es_sesion_nueva(usuario: str) -> bool:
    """True si el usuario no escribió en la última hora (o es su primer mensaje)."""
    ultima = _ultima_actividad.get(usuario)
    if ultima is None:
        return True
    return datetime.now(timezone.utc) - ultima > UMBRAL_SALUDO

CATEGORIAS = [
    "Electricidad",
    "Plomería",
    "Infraestructura",
    "Gas",
    "Pintura",
    "Techos",
    "Pisos",
    "Aberturas",
    "Otro",
]


def _formatear_reclamo(r: Reclamo) -> str:
    fotos_count = len(r.fotos) if r.fotos else 0
    return (
        f"📋 *Reclamo #{r.id}*\n"
        f"🏫 Escuela: {r.nombre_escuela}\n"
        f"📍 Ubicación: {r.ubicacion}\n"
        f"🚦 Prioridad: {r.prioridad.value}\n"
        f"🏷️ Categoría: {r.categoria}\n"
        f"📝 Descripción: {r.descripcion}\n"
        f"📎 Fotos: {fotos_count}\n"
        f"📅 Fecha: {r.fecha_creacion.strftime('%d/%m/%Y %H:%M')}"
    )


def _buscar_por_id(db: Session, reclamo_id: int, usuario: str = "") -> str:
    reclamo = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.fotos))
        .filter(Reclamo.id == reclamo_id)
        .first()
    )
    # Sólo se muestra si el reclamo es de este número (no espiar reclamos ajenos).
    if not reclamo or (usuario and reclamo.telefono_creador != usuario):
        return f"❌ No encontré un reclamo tuyo con ID #{reclamo_id}."
    return _formatear_reclamo(reclamo)


def _procesar_buscar_id(db: Session, usuario: str, mensaje: str) -> str:
    """Maneja el ID que ingresa el usuario tras elegir 'Buscar reclamo'."""
    texto = mensaje.strip().replace("#", "")
    try:
        reclamo_id = int(texto)
    except ValueError:
        return "⚠️ Ingresá solo el número del reclamo (ej: *3*), o *cancelar* para volver."

    del _conversaciones[usuario]
    return _buscar_por_id(db, reclamo_id, usuario)


def _buscar_por_escuela(db: Session, nombre: str) -> str:
    reclamos = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.fotos))
        .filter(Reclamo.nombre_escuela.ilike(f"%{nombre}%"))
        .order_by(Reclamo.fecha_creacion.desc())
        .limit(5)
        .all()
    )
    if not reclamos:
        return f'❌ No encontré reclamos para la escuela "{nombre}".'
    resultado = f"Encontré {len(reclamos)} reclamo(s):\n\n"
    resultado += "\n\n".join(_formatear_reclamo(r) for r in reclamos)
    return resultado


def _listar_recientes(db: Session, usuario: str = "") -> str:
    """Últimos reclamos cargados por este número de WhatsApp."""
    if not usuario:
        return "No pude identificar tu número para buscar tus reclamos."

    reclamos = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.fotos))
        .filter(Reclamo.telefono_creador == usuario)
        .order_by(Reclamo.fecha_creacion.desc())
        .limit(5)
        .all()
    )
    if not reclamos:
        return (
            "Todavía no cargaste ningún reclamo desde este número.\n"
            "Escribí *nuevo* para crear el primero."
        )
    resultado = "📋 *Tus últimos reclamos:*\n\n"
    for r in reclamos:
        resultado += (
            f"• #{r.id} | {r.nombre_escuela} | {r.prioridad.value} | "
            f"{r.categoria} | {r.fecha_creacion.strftime('%d/%m/%Y')}\n"
        )
    resultado += "\nPara ver el detalle, escribí: *ver #<id>*"
    return resultado


def _mostrar_ayuda(variante: str = "menu"):
    """Menú principal con botones.

    `variante` cambia el texto de encabezado:
    - "saludo": bienvenida cálida (primer contacto o regreso tras un rato)
    - "menu": menú neutro (cuando piden ayuda/menú explícitamente)
    - "no_entendi": aclara que no se reconoció el mensaje y ofrece las opciones
    """
    if variante == "saludo":
        body = (
            "👋 ¡Hola! Soy *InfraBot*, tu asistente para la gestión de reclamos de "
            "infraestructura escolar.\n\n"
            "Estoy acá para ayudarte a cargar un nuevo reclamo o consultar el estado de "
            "los que ya existen.\n\n"
            "¿Qué te gustaría hacer?"
        )
    elif variante == "no_entendi":
        body = "🤖 No entendí tu mensaje. Estas son las opciones disponibles:"
    else:
        body = "🤖 *InfraBot*\n\n¿Qué querés hacer?"

    return {
        "tipo": "botones",
        "body": body,
        "botones": [
            {"id": "nuevo", "title": "📝 Nuevo reclamo"},
            {"id": "recientes", "title": "📋 Ver recientes"},
            {"id": "buscar_reclamo", "title": "🔍 Buscar reclamo"},
        ],
    }


# --- Flujo de creación de reclamo ---

def _iniciar_creacion(usuario: str) -> str:
    _conversaciones[usuario] = {"paso": "escuela", "datos": {}, "media": []}
    return (
        "📝 *Nuevo Reclamo*\n\n"
        "Vamos a cargar un reclamo paso a paso.\n"
        "Podés escribir *cancelar* en cualquier momento para salir.\n\n"
        "🏫 *Paso 1/4:* ¿Cuál es el nombre de la escuela?"
    )


def _procesar_creacion(db: Session, usuario: str, mensaje: str) -> str:
    conv = _conversaciones[usuario]
    paso = conv["paso"]
    datos = conv["datos"]
    texto = mensaje.strip()

    if paso == "escuela":
        if len(texto) < 3:
            return "⚠️ El nombre debe tener al menos 3 caracteres. Intentá de nuevo:"
        datos["nombre_escuela"] = texto
        conv["paso"] = "ubicacion"
        return "📍 *Paso 2/4:* ¿Cuál es la ubicación? (dirección o referencia)"

    if paso == "ubicacion":
        if len(texto) < 2:
            return "⚠️ La ubicación debe tener al menos 2 caracteres. Intentá de nuevo:"
        datos["ubicacion"] = texto
        conv["paso"] = "descripcion"
        return "📝 *Paso 3/4:* Describí el problema (mínimo 10 caracteres):"

    if paso == "descripcion":
        if len(texto) < 10:
            return "⚠️ La descripción debe tener al menos 10 caracteres. Intentá de nuevo:"
        datos["descripcion"] = texto
        datos["categoria"] = "Sin clasificar"
        datos["prioridad"] = "MEDIA"
        conv["paso"] = "media"
        media_count = len(conv.get("media", []))
        if media_count > 0:
            return (
                f"📎 *Paso 4/4:* Ya tenés {media_count} archivo(s) adjunto(s).\n"
                "Podés enviar más fotos/videos o escribí *listo* para continuar."
            )
        return (
            "📎 *Paso 4/4:* Enviá fotos o videos del problema (opcional).\n"
            "Podés enviar varios. Cuando termines, escribí *listo*."
        )

    if paso == "media":
        if texto.lower() in ("listo", "continuar", "siguiente", "ok"):
            conv["paso"] = "confirmacion"
            media_count = len(conv.get("media", []))
            resumen = (
                "✅ *Resumen del reclamo:*\n\n"
                f"🏫 Escuela: {datos['nombre_escuela']}\n"
                f"📍 Ubicación: {datos['ubicacion']}\n"
                f"📝 Descripción: {datos['descripcion']}\n"
                f"📎 Archivos: {media_count}\n\n"
                "¿Confirmás la carga?"
            )
            return {
                "tipo": "botones",
                "body": resumen,
                "botones": [
                    {"id": "si", "title": "✅ Confirmar"},
                    {"id": "no", "title": "❌ Cancelar"},
                ],
            }
        return "📎 Enviá fotos/videos o escribí *listo* para continuar."

    if paso == "confirmacion":
        texto_lower = texto.lower()
        if texto_lower in ("si", "sí", "s", "yes", "confirmar"):
            # Crear el reclamo en la base de datos
            nuevo = Reclamo(
                nombre_escuela=datos["nombre_escuela"],
                ubicacion=datos["ubicacion"],
                prioridad=PrioridadReclamo(datos["prioridad"]),
                categoria=datos["categoria"],
                descripcion=datos["descripcion"],
                telefono_creador=usuario or None,
            )
            db.add(nuevo)
            db.commit()
            db.refresh(nuevo)

            # Guardar archivos multimedia asociados
            media_guardados = 0
            for m in conv.get("media", []):
                tipo = TipoMedia.VIDEO if "video" in m["mime_type"] else TipoMedia.IMAGEN
                foto = FotoReclamo(
                    reclamo_id=nuevo.id,
                    nombre_archivo=m["url"].split("/")[-1],
                    url=m["url"],
                    tipo=tipo,
                )
                db.add(foto)
                media_guardados += 1
            if media_guardados > 0:
                db.commit()

            del _conversaciones[usuario]
            media_txt = f"\n📎 Archivos adjuntos: {media_guardados}" if media_guardados else ""
            return (
                f"🎉 *¡Reclamo #{nuevo.id} creado exitosamente!*\n\n"
                f"{_formatear_reclamo(nuevo)}{media_txt}\n\n"
                f"Podés ver su estado con: *ver #{nuevo.id}*"
            )
        elif texto_lower in ("no", "n", "cancelar"):
            del _conversaciones[usuario]
            return "❌ Carga cancelada. Escribí *nuevo* para empezar de nuevo."
        else:
            return "Escribí *si* para confirmar o *no* para cancelar:"

    # Estado desconocido, limpiar
    del _conversaciones[usuario]
    return "⚠️ Ocurrió un error. Escribí *nuevo* para empezar de nuevo."


def iniciar_espera_info(telefono_creador: str, reclamo_id: int) -> None:
    """Deja al creador del reclamo esperando que responda con información adicional.

    Lo llama el endpoint de solicitar-información. Los próximos mensajes (texto o media)
    de ese número se agregan al reclamo hasta que escriba *listo*.
    """
    _conversaciones[telefono_creador] = {
        "paso": "info_adicional",
        "reclamo_id": reclamo_id,
        "media": [],
    }


def _procesar_info_adicional(db: Session, usuario: str, mensaje: str) -> str:
    """Maneja los mensajes de texto del creador mientras aporta información adicional."""
    conv = _conversaciones[usuario]
    reclamo_id = conv["reclamo_id"]
    texto = mensaje.strip()

    if texto.lower() in ("listo", "terminar", "fin", "ok", "gracias"):
        del _conversaciones[usuario]
        return (
            f"✅ ¡Gracias! Sumé tu información al reclamo #{reclamo_id}. "
            "El contratista ya va a poder verla."
        )

    reclamo = db.get(Reclamo, reclamo_id)
    if reclamo is None:
        del _conversaciones[usuario]
        return "⚠️ No encontré el reclamo. Escribí *ayuda* para ver los comandos."

    # Anexar el texto a las observaciones del reclamo
    prefijo = "\n\n" if reclamo.observaciones else ""
    fecha = datetime.now(ART).strftime("%d/%m/%Y %H:%M")
    reclamo.observaciones = (
        (reclamo.observaciones or "") + f"{prefijo}[Info adicional {fecha}] {texto}"
    )
    db.commit()

    return (
        "📝 Anoté tu respuesta en el reclamo.\n"
        "Podés seguir enviando texto o fotos/videos, o escribí *listo* cuando termines."
    )


def procesar_mensaje(db: Session, mensaje: str, usuario: str = "") -> str:
    """Recibe un mensaje de texto y devuelve la respuesta del bot."""
    texto = mensaje.strip().lower()

    # Anti-spam: si ya está bloqueado, no responder (evita seguir alimentando el flood).
    if usuario and _esta_bloqueado(usuario):
        return ""

    # Registrar el mensaje y ver si con este superó el límite.
    if usuario and _registrar_y_chequear_flood(usuario):
        return (
            "⚠️ Estás enviando demasiados mensajes muy rápido. "
            "Esperá unos minutos antes de volver a escribir."
        )

    # Evaluar si es una sesión nueva ANTES de registrar esta interacción.
    sesion_nueva = _es_sesion_nueva(usuario)
    if usuario:
        _ultima_actividad[usuario] = datetime.now(timezone.utc)

    # Cancelar siempre funciona
    if texto == "cancelar" and usuario in _conversaciones:
        del _conversaciones[usuario]
        return "❌ Operación cancelada. Escribí *ayuda* para ver los comandos."

    # Si el creador está aportando información adicional a un reclamo
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "info_adicional":
        return _procesar_info_adicional(db, usuario, mensaje)

    # Si el usuario está esperando ingresar un ID para buscar un reclamo
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "buscar_id":
        return _procesar_buscar_id(db, usuario, mensaje)

    # Si el usuario está en medio de una conversación de creación
    if usuario in _conversaciones:
        return _procesar_creacion(db, usuario, mensaje)

    # Comando: nuevo reclamo
    if texto in ("nuevo", "crear", "cargar", "nuevo reclamo"):
        return _iniciar_creacion(usuario)

    # Botón: buscar reclamo → pedir el ID
    if texto == "buscar_reclamo":
        _conversaciones[usuario] = {"paso": "buscar_id"}
        return (
            "🔍 Escribí el número (ID) del reclamo que querés ver.\n"
            "Por ejemplo: *3*\n\n"
            "Escribí *cancelar* para volver."
        )

    # Comando: ver #<id>
    if texto.startswith("ver #") or texto.startswith("ver#"):
        try:
            id_str = texto.replace("ver#", "").replace("ver #", "").strip()
            reclamo_id = int(id_str)
            return _buscar_por_id(db, reclamo_id, usuario)
        except (ValueError, IndexError):
            return "⚠️ Formato incorrecto. Usá: *ver #<id>*\nEjemplo: ver #3"

    # Comando: buscar <escuela>
    if texto.startswith("buscar "):
        nombre = mensaje.strip()[7:].strip()
        if len(nombre) < 2:
            return "⚠️ Escribí al menos 2 caracteres para buscar.\nEjemplo: buscar Escuela Técnica"
        return _buscar_por_escuela(db, nombre)

    # Comando: recientes / últimos → solo los reclamos de este número
    if texto in ("recientes", "últimos", "ultimos", "listar"):
        return _listar_recientes(db, usuario)

    # Saludos → bienvenida cálida solo la primera vez en el rango; si repite, "no entendí"
    if texto in ("hola", "hi", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches"):
        return _mostrar_ayuda(variante="saludo" if sesion_nueva else "no_entendi")

    # Comando: ayuda / help / menú → menú directo
    if texto in ("ayuda", "help", "menu", "menú", "inicio"):
        return _mostrar_ayuda(variante="menu")

    # Comando: más comandos (desde botón)
    if texto == "ayuda_texto":
        return (
            "📖 *Comandos adicionales:*\n\n"
            "• *ver #<id>* — Ver detalle de un reclamo\n"
            "• *buscar <escuela>* — Buscar por escuela\n"
            "• *cancelar* — Cancelar operación en curso\n\n"
            "Ejemplos:\n"
            "  ver #3\n"
            "  buscar Escuela Técnica"
        )

    # Si el mensaje es un número solo, asumir que quieren ver ese reclamo
    try:
        reclamo_id = int(texto.replace("#", "").strip())
        return _buscar_por_id(db, reclamo_id, usuario)
    except ValueError:
        pass

    # Mensaje no reconocido. Si vuelve tras un rato (o es su primera vez) lo recibimos
    # con la bienvenida; si es dentro de la conversación, aclaramos que no entendimos.
    # En ambos casos ofrecemos las opciones con botones.
    return _mostrar_ayuda(variante="saludo" if sesion_nueva else "no_entendi")


def procesar_media(db: Session, usuario: str, url_local: str, mime_type: str, caption: str = "") -> str:
    """Procesa un archivo multimedia recibido por WhatsApp.

    Si el usuario está en el flujo de creación de reclamo, lo agrega como adjunto.
    Si no, le indica que primero inicie un reclamo.
    """
    # Anti-spam: mismo tratamiento que los mensajes de texto.
    if usuario and _esta_bloqueado(usuario):
        return ""

    if usuario and _registrar_y_chequear_flood(usuario):
        return (
            "⚠️ Estás enviando demasiados mensajes muy rápido. "
            "Esperá unos minutos antes de volver a escribir."
        )

    if usuario:
        _ultima_actividad[usuario] = datetime.now(timezone.utc)

    # Si el creador está aportando información adicional, guardar el archivo en el reclamo
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "info_adicional":
        conv = _conversaciones[usuario]
        reclamo = db.get(Reclamo, conv["reclamo_id"])
        if reclamo is None:
            del _conversaciones[usuario]
            return "⚠️ No encontré el reclamo. Escribí *ayuda* para ver los comandos."

        tipo = TipoMedia.VIDEO if "video" in mime_type else TipoMedia.IMAGEN
        foto = FotoReclamo(
            reclamo_id=reclamo.id,
            nombre_archivo=url_local.split("/")[-1],
            url=url_local,
            tipo=tipo,
        )
        db.add(foto)
        db.commit()
        tipo_str = "📹 Video" if "video" in mime_type else "📷 Foto"
        return (
            f"{tipo_str} agregada al reclamo #{reclamo.id} ✅\n"
            "Podés seguir enviando o escribí *listo* cuando termines."
        )

    # Si está en el flujo de creación, agregar el media
    if usuario in _conversaciones:
        conv = _conversaciones[usuario]
        paso = conv["paso"]

        # Aceptar media en cualquier paso del flujo de creación
        if paso in ("escuela", "ubicacion", "descripcion", "media", "confirmacion"):
            conv.setdefault("media", []).append({
                "url": url_local,
                "mime_type": mime_type,
            })
            count = len(conv["media"])
            tipo_str = "📹 Video" if "video" in mime_type else "📷 Foto"

            if paso == "media":
                return (
                    f"{tipo_str} recibida ✅ (total: {count})\n"
                    "Podés seguir enviando o escribí *listo* para continuar."
                )
            else:
                return (
                    f"{tipo_str} recibida ✅ (total: {count})\n"
                    "La guardé para adjuntarla al reclamo. Seguí con el paso actual."
                )

    # No está en ningún flujo
    return (
        "📎 Recibí tu archivo, pero no tenés un reclamo en curso.\n"
        "Escribí *nuevo* para crear un reclamo y poder adjuntar fotos/videos."
    )
