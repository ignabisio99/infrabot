"""Lógica conversacional del bot de WhatsApp.

Interpreta los mensajes entrantes y genera respuestas consultando
la base de datos de reclamos. Soporta un flujo de creación de
reclamos paso a paso.
"""

import logging
import os
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session, joinedload

from core import reloj
from core.ai import config as ai_config
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.reclamo import EstadoReclamo, PrioridadReclamo, Reclamo
from models.recordatorio_contratista import RecordatorioContratista
from models.visita import Visita
from models.recomendacion_ia import TipoRecomendacionIA
from services import avance_contratista, estados_reclamo
from services.ai import (
    clasificacion,
    completitud,
    duplicados,
    extraccion_reclamo,
    registro,
    stt,
)
from services.ai.automatico import post_alta_reclamo, post_fotos_reclamo

logger = logging.getLogger(__name__)

# Zona horaria UTC-3 (Argentina), para los timestamps de la info adicional.
ART = timezone(timedelta(hours=-3))

APP_URL = os.getenv("APP_URL", "http://localhost:3000")

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

_SALUDOS_INICIO = (
    "buenos dias",
    "buenos días",
    "buenas tardes",
    "buenas noches",
    "hola",
    "buenas",
    "hi",
    "che",
)


def _normalizar_comando(texto: str) -> str:
    """Minúsculas y sin signos alrededor: '¡Listo!' → 'listo'."""
    t = (texto or "").strip().lower()
    return re.sub(r"^[^\wáéíóúüñ]+|[^\wáéíóúüñ]+$", "", t, flags=re.UNICODE)


def _es_comando(texto: str, *opciones: str) -> bool:
    return _normalizar_comando(texto) in opciones


def _es_comando_listo(texto: str) -> bool:
    if _es_comando(texto, "listo", "continuar", "siguiente", "ok"):
        return True
    norm = _normalizar_comando(texto)
    palabras = norm.split()
    if not palabras or len(palabras) > 3:
        return False
    # Whisper a veces devuelve "lito" / "lito lito chatelito" por "listo".
    return _similitud(palabras[0], "listo") >= 0.75


def _similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# CU-05: respuestas afirmativas/negativas a las preguntas de seguimiento (botones o texto).
# Las preguntas las manda el bot de forma proactiva (schedulers); acá se interpreta la
# respuesta, ya sea un botón (llega el id, ver services.cu05_botones) o texto libre.


def _es_confirmacion_si(texto: str) -> bool:
    from services import cu05_botones

    if (texto or "").strip() in (
        cu05_botones.INICIO_SI, cu05_botones.TERMINO_SI, cu05_botones.RESUELTO_SI
    ):
        return True
    return _es_comando(
        texto, "si", "sí", "sip", "dale", "ok", "listo", "terminé", "termine",
        "confirmo", "confirmar", "correcto", "exacto", "resuelto", "solucionado",
        "empecé", "empece", "arranqué", "arranque",
    )


def _es_confirmacion_no(texto: str) -> bool:
    from services import cu05_botones

    if (texto or "").strip() in (
        cu05_botones.INICIO_NO, cu05_botones.TERMINO_NO, cu05_botones.RESUELTO_NO
    ):
        return True
    return _es_comando(
        texto, "no", "nop", "todavía no", "todavia no", "aún no", "aun no",
        "no pude", "no del todo",
    )


def _es_reporte_termino(texto: str) -> bool:
    """Detecta si el contratista indica que terminó o finalizó el trabajo."""
    t = _normalizar_comando(texto or "")
    if not t:
        return False
    # Negaciones explícitas no son término ("no terminé", "todavía no", etc.)
    if re.search(r"\b(no|todav[ií]a no|a[uú]n no|no pude)\b", t):
        return False

    comandos_directos = {
        "terminé", "termine", "terminamos", "terminado", "terminada",
        "finalicé", "finalice", "finalizamos", "finalizado", "finalizada",
        "listo", "lista",
        "ya terminé", "ya termine", "ya terminamos", "ya finalicé", "ya finalice",
        "ya está listo", "ya esta listo", "ya está", "ya esta",
        "trabajo terminado", "trabajo listo", "obra terminada", "obra lista",
        "cu05_termino_si",
    }
    if t in comandos_directos:
        return True

    # Patrones por regex para frases como "ya terminé el trabajo", "terminamos la obra"
    if re.search(r"\b(termin[eé]|terminamos|terminado|finalic[eé]|finalizamos|finalizado)\b", t):
        return True
    if re.search(r"\b(ya est[aá] listo|trabajo listo|obra lista|qued[oó] listo)\b", t):
        return True

    return False


def _sin_saludo_inicial(texto: str) -> str:
    resto = (texto or "").strip()
    while resto:
        bajo = resto.lower()
        matcheo = False
        for saludo in sorted(_SALUDOS_INICIO, key=len, reverse=True):
            if bajo == saludo:
                return ""
            if bajo.startswith(saludo) and bajo[len(saludo) : len(saludo) + 1] in ("", " ", ",", ".", "!", "¡", "?", "¿", ";", ":"):
                resto = resto[len(saludo) :].lstrip(" ,.;:¡!¿?")
                matcheo = True
                break
        if not matcheo:
            break
    return resto.strip()


# Conectores / presentación. No es un catálogo de desperfectos: sirve para
# ignorar "hola, soy de la escuela 5" y dejar pasar cualquier relato real.
_RELLENO_PRESENTACION = frozenset({
    "hola", "buenas", "buen", "buenos", "dias", "días", "tardes", "noches",
    "mira", "mirá", "che", "eh", "mm", "bueno", "ok", "dale", "gracias",
    "este", "esta", "esto", "ese", "esa", "eso", "aqui", "aquí", "aca", "acá",
    "ahi", "ahí", "alla", "allá",
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "en", "al", "a", "y", "o", "u", "que", "qué", "si", "sí",
    "no", "por", "con", "para", "se", "me", "mi", "tu", "su", "les", "le",
    "es", "son", "soy", "somos", "estoy", "estamos", "esta", "está",
    "ser", "estar",
    "numero", "número", "nro", "n", "escuela", "colegio", "jardin", "jardín",
    "pero", "como", "cómo", "cuando", "cuándo", "donde", "dónde",
    "yo", "nosotros", "usted", "ustedes", "hola",
})


def _palabras_contenido(texto: str) -> list[str]:
    resto = _sin_saludo_inicial(texto).lower()
    resto = re.sub(r"[^\wáéíóúüñ\s]", " ", resto, flags=re.UNICODE)
    out: list[str] = []
    for p in resto.split():
        if not p or p.isdigit() or p in _RELLENO_PRESENTACION:
            continue
        out.append(p)
    return out


def _parece_solo_presentacion(texto: str) -> bool:
    """True si no hay relato: saludo, nombrarse o decir de qué escuela es."""
    resto = _sin_saludo_inicial(texto)
    if len(resto) < 8:
        return True
    return len(_palabras_contenido(texto)) <= 1


def _parece_relato(texto: str) -> bool:
    """Hay sustancia más allá de presentarse (cualquier redacción)."""
    return not _parece_solo_presentacion(texto)


def _parece_descripcion_reclamo(mensaje: str) -> bool:
    """True si además de un saludo ya cuenta algo (no solo 'hola' o 'escuela 5')."""
    resto = _sin_saludo_inicial(mensaje)
    return len(resto) >= 10 and _parece_relato(mensaje)


def _descripcion_debil(texto: str, escuela: str | None = None) -> bool:
    if _parece_solo_presentacion(texto):
        return True
    t = _sin_saludo_inicial(texto).strip()
    if len(t) < 12:
        return True
    if escuela:
        esc = re.sub(r"[^\wáéíóúüñ\s]", " ", escuela.lower())
        if esc and esc in t.lower() and len(_palabras_contenido(t)) <= 2:
            return True
    return False


def _acumular_nota(datos: dict, texto: str) -> None:
    t = (texto or "").strip()
    if not t:
        return
    if _es_comando_listo(t) or _es_comando(
        t, "si", "sí", "s", "no", "cancelar", "ok", "dale"
    ):
        return
    bajo = t.lower()
    if bajo.startswith("escuela_") or bajo.startswith("esc_"):
        return
    notas: list = datos.setdefault("notas", [])
    if t not in notas:
        notas.append(t)


def _fusionar_descripcion(actual: str | None, nuevo: str | None) -> str:
    a = (actual or "").strip()
    n = (nuevo or "").strip()
    if not n:
        return a
    if not a:
        return n
    if n.lower() in a.lower():
        return a
    if a.lower() in n.lower():
        return n
    return f"{a}\n{n}".strip()


def _incorporar_detalle(datos: dict, texto: str) -> None:
    """Cualquier relato en cualquier paso se guarda; no se filtra por vocabulario."""
    _acumular_nota(datos, texto)
    if not _parece_relato(texto):
        return
    datos["descripcion"] = _fusionar_descripcion(datos.get("descripcion"), texto)


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


def reiniciar_conversacion(usuario: str) -> None:
    """Borra el estado en memoria de un número (simulador: nueva charla)."""
    _conversaciones.pop(usuario, None)
    _ultima_actividad.pop(usuario, None)
    _historial_mensajes.pop(usuario, None)
    _bloqueados_hasta.pop(usuario, None)


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

# Etiquetas legibles del estado del reclamo para mostrar por WhatsApp.
ETIQUETA_ESTADO = {
    "PENDIENTE_REVISION": "En revisión",
    "PENDIENTE_PRESUPUESTO": "Pendiente de presupuesto",
    "EN_EVALUACION": "En evaluación de presupuestos",
    "APROBADO": "Presupuesto aprobado",
    "PENDIENTE_COORDINACION": "Coordinando la visita",
    "VISITA_COORDINADA": "Visita agendada",
    "EN_EJECUCION": "En ejecución",
    "PENDIENTE_INTERVENCION": "Pendiente de intervención",
    "FINALIZADO": "Finalizado",
    "DESIERTO": "Sin ofertas",
    "RECHAZADO": "Rechazado",
    "CANCELADO": "Cancelado",
}


def _etiqueta_estado(reclamo: Reclamo) -> str:
    valor = reclamo.estado.value if reclamo.estado else ""
    return ETIQUETA_ESTADO.get(valor, valor)


def _limpiar_espacios(texto: str) -> str:
    """Colapsa espacios múltiples y recorta extremos.

    El padrón de escuelas trae domicilios con dobles espacios (ej: 'MENDOZA 1069  BARRIO')
    que rompen el formato de WhatsApp (deja los _ o * crudos) y quedan feos en el reclamo.
    """
    return " ".join(str(texto or "").split())


def _encolar_post_ia(db: Session, reclamo_id: int) -> None:
    """Encola el análisis de IA para correr en segundo plano (no bloquea el resumen).

    Si Redis no está disponible (ej. dev sin Redis), corre la IA inline como fallback
    para no perder el análisis; en ese caso el resumen sí espera, pero es aceptable.
    """
    from services.cola_whatsapp import encolar

    if encolar({"kind": "post_ia", "reclamo_id": reclamo_id}):
        return
    # Fallback sin Redis: correr inline.
    try:
        reclamo = db.get(Reclamo, reclamo_id)
        if reclamo is not None:
            post_alta_reclamo(db, reclamo)
            recargado = (
                db.query(Reclamo)
                .options(joinedload(Reclamo.fotos))
                .filter(Reclamo.id == reclamo_id)
                .first()
            )
            if recargado is not None:
                post_fotos_reclamo(db, recargado)
            db.commit()
    except Exception:
        logger.exception("post_ia inline falló para reclamo %s", reclamo_id)
        db.rollback()


def _mensaje_paso_media(conv: dict) -> str:
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


def _tras_descripcion_o_completitud(db: Session, conv: dict, datos: dict):
    """Tras descripción (o respuesta a faltante): valida completitud o avanza a media."""
    rondas = int(conv.get("faltantes_rondas") or 0)
    if rondas >= completitud.MAX_RONDAS_FALTANTES:
        datos["observaciones"] = (
            (datos.get("observaciones") or "")
            + " [IA] Completitud parcial: se alcanzó el máximo de preguntas."
        ).strip()
        return _avanzar_a_media_o_duplicados(db, conv, datos)

    resultado = completitud.evaluar_completitud(
        escuela=datos.get("nombre_escuela") or "",
        ubicacion=datos.get("ubicacion") or "",
        descripcion=datos.get("descripcion") or "",
        info_extra=datos.get("info_extra") or "",
    )

    if resultado.completo or not resultado.faltantes:
        conv.pop("faltante_campo", None)
        return _avanzar_a_media_o_duplicados(db, conv, datos)

    # Se pregunta solo la primera faltante y se re-evalúa en la próxima respuesta con todo
    # lo que el usuario ya aportó. Así no se repregunta algo que recién fue respondido.
    primera = resultado.faltantes[0]
    conv["paso"] = "faltantes"
    conv["faltante_campo"] = primera.campo
    return f"❓ {primera.pregunta}"


def _chequear_duplicados(db: Session, datos: dict) -> list:
    """Busca reclamos similares ya cargados a partir de los datos parciales del bot.

    Construye un Reclamo en memoria (sin persistirlo) con lo que el usuario viene
    ingresando y reutiliza services.ai.duplicados.buscar_duplicados. Devuelve la lista
    de candidatos (posiblemente vacía). Nunca lanza: ante cualquier error devuelve [].
    """
    try:
        tentativo = Reclamo(
            nombre_escuela=datos.get("nombre_escuela") or "",
            ubicacion=datos.get("ubicacion") or "",
            prioridad=PrioridadReclamo(datos.get("prioridad") or "MEDIA"),
            categoria=datos.get("categoria") or "Sin clasificar",
            descripcion=datos.get("descripcion") or "",
        )
        # id=None hace que buscar_duplicados no se excluya a sí mismo; como no está
        # persistido, ningún candidato real tendrá id None, así que el filtro id != es seguro.
        return duplicados.buscar_duplicados(db, tentativo, limite=3)
    except Exception:
        return []


def _avanzar_a_media_o_duplicados(db: Session, conv: dict, datos: dict):
    """Antes de pedir fotos, corta la carga si el reclamo ya fue reportado.

    Si encuentra un reclamo similar en la misma escuela, NO deja crear el duplicado:
    informa cuál es el reclamo existente y ofrece verlo o cerrar. Si no hay similares,
    sigue el flujo normal hacia el paso de fotos.
    """
    candidatos = _chequear_duplicados(db, datos)
    if candidatos:
        conv["paso"] = "confirmar_duplicado"
        top = candidatos[0]
        estado_txt = top.estado.value.replace("_", " ").lower()
        otros = ""
        if len(candidatos) > 1:
            otros = f"\n(hay {len(candidatos) - 1} reclamo/s más parecido/s)"
        return {
            "tipo": "botones",
            "body": (
                "⚠️ *Este problema ya fue reportado.*\n\n"
                f"Ya existe el *Reclamo #{top.reclamo_id}* en la misma escuela:\n"
                f"🏷️ {top.categoria}\n"
                f"📊 Estado: {estado_txt}\n"
                f"📝 {top.descripcion[:180]}{otros}\n\n"
                "Para evitar reclamos repetidos, no se puede cargar de nuevo. "
                "Podés seguir el estado del que ya existe."
            ),
            "botones": [
                {"id": "dup_ver", "title": f"👀 Ver #{top.reclamo_id}"},
                {"id": "dup_cerrar", "title": "✅ Entendido"},
            ],
        }

    conv["paso"] = "media"
    return _mensaje_paso_media(conv)


def _procesar_confirmar_duplicado(db: Session, usuario: str, conv: dict, datos: dict, texto: str):
    """Maneja la respuesta del usuario tras avisarle de que el reclamo ya existe.

    No hay opción de "cargar igual": el objetivo es justamente no duplicar. El usuario
    puede ver el reclamo existente o cerrar la conversación.
    """
    opcion = texto.strip().lower()

    if opcion.startswith("dup_ver") or opcion.startswith("ver"):
        candidatos = _chequear_duplicados(db, datos)
        if candidatos:
            top = candidatos[0]
            estado_txt = top.estado.value.replace("_", " ").lower()
            # No se usa _buscar_por_id porque el duplicado puede ser de otra persona
            # (ese helper oculta reclamos ajenos). Mostramos lo que ya conocemos.
            detalle = (
                f"📋 *Reclamo #{top.reclamo_id}*\n"
                f"🏫 Escuela: {top.nombre_escuela}\n"
                f"🏷️ Categoría: {top.categoria}\n"
                f"📊 Estado: {estado_txt}\n"
                f"📝 {top.descripcion}"
            )
            del _conversaciones[usuario]
            return (
                f"{detalle}\n\n"
                f"Podés seguir su estado con: *ver #{top.reclamo_id}*"
            )
        # Ya no hay candidatos (raro): cerrar la conversación sin crear nada.
        del _conversaciones[usuario]
        return "No encontré el reclamo relacionado. Escribí *nuevo* si querés empezar de nuevo."

    # Cualquier otra respuesta (dup_cerrar, "entendido", "ok", "cancelar", etc.) cierra.
    del _conversaciones[usuario]
    return (
        "👌 Listo, no cargué un reclamo repetido. "
        "Escribí *nuevo* si querés reportar otra cosa distinta."
    )


def _formatear_reclamo(r: Reclamo) -> str:
    fotos_count = len(r.fotos) if r.fotos else 0
    return (
        f"📋 *Reclamo #{r.id}*\n"
        f"🏫 Escuela: {r.nombre_escuela}\n"
        f"📍 Ubicación: {r.ubicacion}\n"
        f"📊 Estado: {_etiqueta_estado(r)}\n"
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
            f"• #{r.id} | {r.nombre_escuela}\n"
            f"   📊 {_etiqueta_estado(r)} | 🚦 {r.prioridad.value} | "
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
        body = (
            "🤖 No entendí tu mensaje. Estas son las opciones disponibles.\n\n"
            "También podés tocar *Hablar con humano* o escribir *operador*."
        )
    else:
        body = "🤖 *InfraBot*\n\n¿Qué querés hacer?"

    # WhatsApp admite 3 botones. El tercero es siempre pasar a un humano;
    # buscar/recientes siguen por texto (*ver #<id>*, *recientes*).
    if ai_config.ai_whatsapp_enabled():
        botones = [
            {"id": "libre", "title": "💬 Contame el problema"},
            {"id": "nuevo", "title": "📝 Nuevo reclamo"},
            {"id": "operador", "title": "🙋 Hablar con humano"},
        ]
    else:
        botones = [
            {"id": "nuevo", "title": "📝 Nuevo reclamo"},
            {"id": "recientes", "title": "📋 Ver recientes"},
            {"id": "operador", "title": "🙋 Hablar con humano"},
        ]

    return {
        "tipo": "botones",
        "body": body,
        "botones": botones,
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


def _iniciar_libre(usuario: str) -> str:
    """Modo conversacional IA: el usuario cuenta el problema con sus palabras."""
    _conversaciones[usuario] = {"paso": "libre", "modo": "ia", "datos": {}, "media": []}
    return (
        "💬 *Modo asistido por IA*\n\n"
        "Contame el problema con tus palabras (o mandame un audio): "
        "de qué escuela es, dónde es y qué pasó.\n"
        "Podés escribir *cancelar* en cualquier momento para salir."
    )


def _procesar_escuela_no_encontrada(db: Session, usuario: str, conv: dict, datos: dict, texto: str):
    """Maneja la respuesta cuando la escuela no está en el padrón."""
    opcion = texto.strip().lower()

    if opcion in ("esc_cancelar", "cancelar", "no"):
        del _conversaciones[usuario]
        return "❌ Carga cancelada. Escribí *nuevo* para empezar de nuevo."

    if opcion in ("esc_reingresar", "reingresar", "corregir"):
        conv["paso"] = "escuela"
        return "🏫 Escribí de nuevo el nombre del colegio (revisá que esté bien escrito):"

    if opcion in ("esc_agregar", "agregar", "agregar escuela", "nueva"):
        # Se acepta la escuela tal como la ingresó el usuario (no está en el padrón).
        # Queda registrada en el reclamo; el operador puede sumarla al padrón luego.
        nombre = conv.get("nombre_escuela_ingresado", "").strip()
        datos["nombre_escuela"] = nombre
        datos["observaciones"] = (
            (datos.get("observaciones") or "")
            + f" [Escuela fuera del padrón, ingresada por el usuario: {nombre}]"
        ).strip()
        conv["escuela_confirmada"] = True
        return _tras_fijar_escuela(db, conv, datos)

    return {
        "tipo": "botones",
        "body": "Tocá una opción, por favor:",
        "botones": [
            {"id": "esc_reingresar", "title": "✍️ Reingresar nombre"},
            {"id": "esc_agregar", "title": "➕ Agregar escuela"},
            {"id": "esc_cancelar", "title": "❌ Cancelar"},
        ],
    }


def _confirmar_escuela_padron(db: Session, conv: dict, texto_escuela: str):
    """Busca la escuela en el padrón y arma el diálogo de confirmación con botones.

    Devuelve el mensaje interactivo si hay coincidencias, o None si no hay ninguna
    (en ese caso el llamador sigue con el texto tal cual).
    """
    from services.instituciones import buscar_instituciones

    coincidencias = buscar_instituciones(db, texto_escuela, limite=3)
    if not coincidencias:
        # La escuela no figura en el padrón del Consejo Escolar de San Martín.
        # Avisamos y damos opciones en vez de aceptar el texto en silencio.
        conv["nombre_escuela_ingresado"] = texto_escuela
        conv["paso"] = "escuela_no_encontrada"
        return {
            "tipo": "botones",
            "body": (
                f"⚠️ No encontré *{texto_escuela}* en el Consejo Escolar de San Martín.\n\n"
                "¿El nombre está bien escrito?"
            ),
            "botones": [
                {"id": "esc_reingresar", "title": "✍️ Reingresar nombre"},
                {"id": "esc_agregar", "title": "➕ Agregar escuela"},
                {"id": "esc_cancelar", "title": "❌ Cancelar"},
            ],
        }

    conv["candidatas_escuela"] = [
        {"nombre": i.nombre, "domicilio": i.domicilio, "localidad": i.localidad}
        for i in coincidencias
    ]
    conv["nombre_escuela_ingresado"] = texto_escuela
    conv["paso"] = "confirmar_escuela"
    mejor = coincidencias[0]
    dom = f"\n📍 {mejor.domicilio}" if mejor.domicilio else ""
    loc = f" ({mejor.localidad})" if mejor.localidad else ""
    return {
        "tipo": "botones",
        "body": (
            f"🔎 Encontré este colegio:\n\n"
            f"🏫 *{mejor.nombre}*{dom}{loc}\n\n"
            "¿Es este el colegio del reclamo?"
        ),
        "botones": [
            {"id": "escuela_si", "title": "✅ Sí, es ese"},
            {"id": "escuela_otras", "title": "🔁 Ver otras"},
            {"id": "escuela_no", "title": "✍️ Usar lo que puse"},
        ],
    }


def _siguiente_tras_libre(db: Session, conv: dict, datos: dict) -> str:
    """Tras la extracción libre: pide solo lo que falte y sigue el flujo común."""
    if not datos.get("nombre_escuela"):
        conv["paso"] = "escuela"
        return "🏫 ¿De qué escuela es el reclamo?"

    # Si aún no se confirmó la escuela contra el padrón, hacerlo ahora.
    if not conv.get("escuela_confirmada"):
        dialogo = _confirmar_escuela_padron(db, conv, datos["nombre_escuela"])
        if dialogo is not None:
            return dialogo
        # Sin coincidencias: se toma la escuela extraída tal cual.
        conv["escuela_confirmada"] = True

    if not datos.get("ubicacion"):
        conv["paso"] = "ubicacion"
        return "📍 ¿En qué parte de la escuela es el problema? (aula, piso, sector)"
    return _tras_descripcion_o_completitud(db, conv, datos)


def _procesar_libre(db: Session, conv: dict, datos: dict, texto: str) -> str:
    if len(texto) < 10:
        return "⚠️ Contame un poco más del problema (mínimo 10 caracteres):"

    try:
        extraidos = extraccion_reclamo.extraer_datos_reclamo(texto)
    except Exception:
        extraidos = extraccion_reclamo.DatosReclamoExtraidos(
            nombre_escuela=None,
            ubicacion=None,
            descripcion=texto,
            confianza=0.0,
            proveedor="fallback",
        )

    _acumular_nota(datos, texto)
    if extraidos.nombre_escuela:
        datos["nombre_escuela"] = extraidos.nombre_escuela
    if extraidos.ubicacion:
        datos["ubicacion"] = extraidos.ubicacion
    desc_nueva = (extraidos.descripcion or "").strip()
    if desc_nueva and not _parece_solo_presentacion(desc_nueva):
        datos["descripcion"] = _fusionar_descripcion(datos.get("descripcion"), desc_nueva)
    elif _parece_relato(texto):
        datos["descripcion"] = _fusionar_descripcion(datos.get("descripcion"), texto)
    datos.setdefault("categoria", "Sin clasificar")
    datos.setdefault("prioridad", "MEDIA")
    datos.setdefault("confianza_clasificacion", 0.0)

    if _descripcion_debil(
        datos.get("descripcion") or "", escuela=datos.get("nombre_escuela")
    ):
        conv["paso"] = "libre"
        return (
            "📝 Anoté lo que dijiste. ¿Qué problema hay? "
            "Contame qué no funciona, desde cuándo y si afecta un aula o toda la escuela."
        )

    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.COMPLETITUD,
        payload={
            "modo": "libre",
            "texto_original": texto,
            "nombre_escuela": extraidos.nombre_escuela,
            "ubicacion": extraidos.ubicacion,
            "descripcion": extraidos.descripcion,
            "categoria": datos["categoria"],
            "prioridad": datos["prioridad"],
        },
        proveedor=extraidos.proveedor,
        confianza=extraidos.confianza,
    )
    db.commit()

    return _siguiente_tras_libre(db, conv, datos)


def _procesar_confirmar_escuela(db: Session, conv: dict, datos: dict, texto: str):
    """Maneja la confirmación de la escuela sugerida desde el padrón."""
    opcion = texto.strip().lower()
    candidatas = conv.get("candidatas_escuela", [])

    # Confirmó la primera sugerencia.
    if opcion == "escuela_si":
        elegida = candidatas[0] if candidatas else None
        if elegida:
            datos["nombre_escuela"] = elegida["nombre"]
            if elegida.get("domicilio"):
                conv["sugerencia_ubicacion"] = _limpiar_espacios(elegida["domicilio"])
        return _tras_fijar_escuela(db, conv, datos)

    # Quiere ver las otras coincidencias.
    if opcion == "escuela_otras":
        if len(candidatas) <= 1:
            return {
                "tipo": "botones",
                "body": "No tengo otras coincidencias. ¿Qué querés hacer?",
                "botones": [
                    {"id": "escuela_si", "title": "✅ Usar la sugerida"},
                    {"id": "escuela_no", "title": "✍️ Usar lo que puse"},
                ],
            }
        lineas = "\n".join(
            f"{i + 1}. {c['nombre']}" + (f" — {c['domicilio']}" if c.get("domicilio") else "")
            for i, c in enumerate(candidatas)
        )
        conv["paso"] = "elegir_escuela"
        return (
            f"🔎 Estas son las coincidencias:\n\n{lineas}\n\n"
            "Respondé con el *número* de la correcta, o escribí *ninguna* para usar lo que ingresaste."
        )

    # Prefiere usar exactamente lo que escribió.
    if opcion == "escuela_no":
        datos["nombre_escuela"] = conv.get("nombre_escuela_ingresado", "")
        return _tras_fijar_escuela(db, conv, datos)

    _incorporar_detalle(datos, texto)
    extra = "Anoté lo que contaste. " if _parece_relato(texto) else ""
    return (
        f"{extra}Elegí una opción: *Sí, es ese*, *Ver otras* o *Usar lo que puse* "
        "(tocá uno de los botones)."
    )


def _tras_fijar_escuela(db: Session, conv: dict, datos: dict):
    """Una vez fijada la escuela (confirmada o no), continúa según el modo.

    - Modo IA (libre): marca la escuela como confirmada y sigue el flujo libre.
    - Modo paso a paso: avanza a la ubicación, sugiriendo el domicilio del padrón.
    """
    conv["escuela_confirmada"] = True

    if conv.get("modo") == "ia":
        # La ubicación del reclamo es la dirección del padrón. Lo que el usuario haya
        # dicho sobre el lugar interno (aula, piso) no pisa la dirección: va aparte.
        sug = conv.get("sugerencia_ubicacion")
        if sug:
            if datos.get("ubicacion"):
                datos["info_extra"] = datos["ubicacion"]
            datos["ubicacion"] = sug
        return _continuar_ia(db, conv, datos)

    conv["paso"] = "ubicacion"
    sug = conv.get("sugerencia_ubicacion")
    if sug:
        # Negrita en vez de cursiva: es más tolerante en WhatsApp y no muestra el
        # símbolo crudo. La dirección ya viene con espacios normalizados.
        return (
            f"📍 *Paso 2/4:* La dirección registrada es:\n*{sug}*\n\n"
            "Escribí una referencia más precisa (aula, sector) o mandá *ok* para usar esa."
        )
    return "📍 *Paso 2/4:* ¿Cuál es la ubicación? (dirección o referencia)"


def _continuar_ia(db: Session, conv: dict, datos: dict):
    """Sigue el flujo IA tras fijar la escuela: pide ubicación o pasa a completitud."""
    if not datos.get("ubicacion"):
        conv["paso"] = "ubicacion"
        return "📍 ¿En qué parte de la escuela es el problema? (aula, piso, sector)"
    return _tras_descripcion_o_completitud(db, conv, datos)


def _procesar_elegir_escuela(db: Session, conv: dict, datos: dict, texto: str):
    """El usuario elige una escuela de la lista numerada."""
    candidatas = conv.get("candidatas_escuela", [])
    limpio = texto.strip().lower()

    if limpio in ("ninguna", "no", "0"):
        datos["nombre_escuela"] = conv.get("nombre_escuela_ingresado", "")
        return _tras_fijar_escuela(db, conv, datos)

    try:
        indice = int(limpio.replace("#", ""))
    except ValueError:
        _incorporar_detalle(datos, texto)
        extra = "Anoté lo que contaste. " if _parece_relato(texto) else ""
        return f"{extra}⚠️ Respondé con el número de la opción, o *ninguna*."

    if indice < 1 or indice > len(candidatas):
        return "⚠️ Ese número no está en la lista. Probá de nuevo."

    elegida = candidatas[indice - 1]
    datos["nombre_escuela"] = elegida["nombre"]
    if elegida.get("domicilio"):
        conv["sugerencia_ubicacion"] = _limpiar_espacios(elegida["domicilio"])
    return _tras_fijar_escuela(db, conv, datos)


def _redactar_resumen_reclamo(datos: dict) -> None:
    """Reescribe descripción + notas sueltas en un párrafo claro para el resumen."""
    partes = list(datos.get("notas") or [])
    partes.append(datos.get("descripcion") or "")
    extra = (datos.get("info_extra") or "").strip()
    if extra:
        partes.append(extra)
    seen: set[str] = set()
    unicas: list[str] = []
    for p in partes:
        t = (p or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        unicas.append(t)
    bruto = "\n".join(unicas)
    if not bruto:
        return
    try:
        limpio = extraccion_reclamo.redactar_descripcion(bruto)
    except Exception:
        logger.warning("No se pudo redactar el resumen con el LLM; se limpia en local")
        limpio = extraccion_reclamo.redactar_descripcion_local(bruto)
    if limpio:
        datos["descripcion"] = limpio
        datos.pop("info_extra", None)


def _procesar_creacion(db: Session, usuario: str, mensaje: str) -> str:
    conv = _conversaciones[usuario]
    paso = conv["paso"]
    datos = conv["datos"]
    texto = mensaje.strip()

    if paso == "libre":
        return _procesar_libre(db, conv, datos, texto)

    if paso == "escuela":
        if len(texto) < 3:
            return "⚠️ El nombre debe tener al menos 3 caracteres. Intentá de nuevo:"

        _incorporar_detalle(datos, texto)
        nombre = texto
        if _parece_relato(texto) and len(_palabras_contenido(texto)) >= 3:
            try:
                extraidos = extraccion_reclamo.extraer_datos_reclamo(texto)
            except Exception:
                extraidos = None
            if extraidos and extraidos.nombre_escuela:
                nombre = extraidos.nombre_escuela
            if extraidos and extraidos.ubicacion and not datos.get("ubicacion"):
                datos["ubicacion"] = extraidos.ubicacion
            if extraidos and extraidos.descripcion and not _parece_solo_presentacion(
                extraidos.descripcion
            ):
                datos["descripcion"] = _fusionar_descripcion(
                    datos.get("descripcion"), extraidos.descripcion
                )

        # Buscar la escuela en el padrón para confirmarla con el usuario.
        dialogo = _confirmar_escuela_padron(db, conv, nombre)
        if dialogo is not None:
            return dialogo

        # Sin coincidencias en el padrón: se usa el nombre extraído (o el texto).
        datos["nombre_escuela"] = nombre
        return _tras_fijar_escuela(db, conv, datos)

    if paso == "confirmar_escuela":
        return _procesar_confirmar_escuela(db, conv, datos, texto)

    if paso == "escuela_no_encontrada":
        return _procesar_escuela_no_encontrada(db, usuario, conv, datos, texto)

    if paso == "elegir_escuela":
        return _procesar_elegir_escuela(db, conv, datos, texto)

    if paso == "confirmar_duplicado":
        return _procesar_confirmar_duplicado(db, usuario, conv, datos, texto)

    if paso == "ubicacion":
        if len(texto) < 2:
            return "⚠️ La ubicación debe tener al menos 2 caracteres. Intentá de nuevo:"
        _incorporar_detalle(datos, texto)
        sug = conv.get("sugerencia_ubicacion")
        if sug:
            datos["ubicacion"] = sug
            if not _es_comando(texto, "ok", "si", "sí", "dale", "listo"):
                datos["info_extra"] = texto
        elif _parece_relato(texto) and len(_palabras_contenido(texto)) >= 5:
            # El relato del problema no es una ubicación: se guardó en descripción.
            if not datos.get("ubicacion"):
                conv["paso"] = "ubicacion"
                return "📍 ¿En qué parte de la escuela es el problema? (aula, piso, sector)"
        else:
            datos["ubicacion"] = texto
        if conv.get("modo") == "ia":
            return _siguiente_tras_libre(db, conv, datos)
        conv["paso"] = "descripcion"
        return "📝 *Paso 3/4:* Describí el problema (mínimo 10 caracteres):"

    if paso == "descripcion":
        if len(texto) < 10:
            return "⚠️ La descripción debe tener al menos 10 caracteres. Intentá de nuevo:"
        datos["descripcion"] = _fusionar_descripcion(datos.get("descripcion"), texto)
        try:
            resultado = clasificacion.clasificar_texto(
                datos["descripcion"],
                escuela=datos.get("nombre_escuela"),
                ubicacion=datos.get("ubicacion"),
            )
            datos["categoria"] = resultado.categoria
            datos["prioridad"] = resultado.prioridad.value
            datos["confianza_clasificacion"] = resultado.confianza
        except Exception:
            datos["categoria"] = "Sin clasificar"
            datos["prioridad"] = "MEDIA"
            datos["confianza_clasificacion"] = 0.0

        return _tras_descripcion_o_completitud(db, conv, datos)

    if paso == "faltantes":
        campo_actual = conv.get("faltante_campo") or "descripcion"
        completitud.fusionar_respuesta(datos=datos, campo=campo_actual, respuesta=texto)
        conv["faltantes_rondas"] = int(conv.get("faltantes_rondas") or 0) + 1

        # Re-evaluar con TODO lo aportado hasta ahora (incluye info_extra), para no volver
        # a preguntar algo que el usuario ya respondió en esta misma ronda.
        return _tras_descripcion_o_completitud(db, conv, datos)

    if paso == "media":
        if _es_comando_listo(texto):
            if _descripcion_debil(
                datos.get("descripcion") or "", escuela=datos.get("nombre_escuela")
            ) and datos.get("notas"):
                datos["descripcion"] = _fusionar_descripcion(
                    datos.get("descripcion"),
                    "\n".join(datos.get("notas") or []),
                )
            if _descripcion_debil(
                datos.get("descripcion") or "", escuela=datos.get("nombre_escuela")
            ):
                conv["paso"] = "descripcion" if conv.get("modo") != "ia" else "libre"
                return (
                    "📝 Todavía no tengo claro el problema. "
                    "Contame qué no funciona (agua, luz, techo, etc.)."
                )
            conv["paso"] = "confirmacion"
            media_count = len(conv.get("media", []))
            _redactar_resumen_reclamo(datos)
            # No se muestran categoría ni prioridad: son preliminares y las asigna el
            # sistema al registrar el reclamo. Mostrarlas confundía (podían cambiar).
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
        _incorporar_detalle(datos, texto)
        if _parece_relato(texto):
            return (
                "📝 Anoté esa descripción. Podés mandar fotos o escribir *listo* para continuar."
            )
        return "📎 Enviá fotos/videos o escribí *listo* para continuar."

    if paso == "confirmacion":
        if _es_comando(texto, "si", "sí", "s", "yes", "confirmar"):
            descripcion = datos["descripcion"]
            nuevo = Reclamo(
                nombre_escuela=datos["nombre_escuela"],
                ubicacion=datos["ubicacion"],
                prioridad=PrioridadReclamo(datos["prioridad"]),
                categoria=datos["categoria"],
                descripcion=descripcion,
                observaciones=datos.get("observaciones"),
                telefono_creador=usuario or None,
                estado=estados_reclamo.ESTADO_INICIAL,
            )
            db.add(nuevo)
            estados_reclamo.registrar_estado_inicial(db, nuevo)
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
            db.refresh(nuevo)

            # La IA de análisis (agente: clasificación fundamentada, duplicados, estimación,
            # fotos) corre en SEGUNDO PLANO para que el resumen salga al instante. El resumen
            # ya muestra categoría/prioridad de la clasificación rápida del paso descripción.
            reclamo_id = nuevo.id
            _encolar_post_ia(db, reclamo_id)

            del _conversaciones[usuario]
            media_txt = f"\n📎 Archivos adjuntos: {media_guardados}" if media_guardados else ""
            return (
                f"🎉 *¡Reclamo #{reclamo_id} creado exitosamente!*\n\n"
                f"{_formatear_reclamo(nuevo)}{media_txt}\n\n"
                f"Podés ver su estado con: *ver #{reclamo_id}*"
            )
        elif _es_comando(texto, "no", "n", "cancelar"):
            del _conversaciones[usuario]
            return "❌ Carga cancelada. Escribí *nuevo* para empezar de nuevo."
        else:
            return "Escribí *si* para confirmar o *no* para cancelar:"

    # Estado desconocido, limpiar
    del _conversaciones[usuario]
    return "⚠️ Ocurrió un error. Escribí *nuevo* para empezar de nuevo."


def registrar_estado_conversacion(telefono: str, estado: dict) -> None:
    """Setea el estado conversacional de un número. Lo usan los servicios (visitas)."""
    _conversaciones[telefono] = estado


def iniciar_espera_info(
    telefono_creador: str,
    reclamo_id: int,
    telefono_contratista: str = "",
    nombre_contratista: str = "",
) -> None:
    """Deja al creador del reclamo esperando que responda con información adicional.

    Lo llama el endpoint de solicitar-información. Los próximos mensajes (texto o media)
    de ese número se agregan al reclamo hasta que escriba *listo*. Guarda el contacto
    del contratista que pidió la info para poder avisarle cuando el creador termine.
    """
    _conversaciones[telefono_creador] = {
        "paso": "info_adicional",
        "reclamo_id": reclamo_id,
        "media": [],
        "telefono_contratista": telefono_contratista,
        "nombre_contratista": nombre_contratista,
    }


def _procesar_info_adicional(db: Session, usuario: str, mensaje: str) -> str:
    """Maneja los mensajes de texto del creador mientras aporta información adicional."""
    conv = _conversaciones[usuario]
    reclamo_id = conv["reclamo_id"]
    texto = mensaje.strip()

    if _es_comando(texto, "listo", "terminar", "fin", "ok", "gracias"):
        telefono_contratista = conv.get("telefono_contratista")
        nombre_contratista = conv.get("nombre_contratista", "")
        del _conversaciones[usuario]

        reclamo = db.get(Reclamo, reclamo_id)
        if reclamo is not None:
            try:
                post_alta_reclamo(db, reclamo)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "No se pudo recalcular la IA tras info adicional del reclamo %s",
                    reclamo_id,
                )

        # Avisar al contratista que ya está disponible la información que había pedido.
        if telefono_contratista:
            from core.whatsapp_client import enviar_mensaje

            escuela = reclamo.nombre_escuela if reclamo else ""
            link = f"{APP_URL}/portal/reclamos/{reclamo_id}/presupuestar"
            aviso = (
                f"✅ *Información actualizada — Reclamo #{reclamo_id}*\n\n"
                f"🏫 Escuela: {escuela}\n\n"
                "La persona que creó el reclamo cargó la información adicional que "
                "habías solicitado. Ya podés revisarla y continuar con tu presupuesto.\n\n"
                f"Ingresá desde acá:\n{link}"
            )
            try:
                enviar_mensaje(telefono_contratista, aviso)
            except Exception as e:  # noqa: BLE001 - no romper el flujo del creador si falla el aviso
                print(f"[WHATSAPP] No se pudo avisar al contratista: {e}")

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
    fecha = reloj.formatear_art()
    reclamo.observaciones = (
        (reclamo.observaciones or "") + f"{prefijo}[Info adicional {fecha}] {texto}"
    )
    db.commit()

    return (
        "📝 Anoté tu respuesta en el reclamo.\n"
        "Podés seguir enviando texto o fotos/videos, o escribí *listo* cuando termines."
    )


def _procesar_visita_disponibilidad(db: Session, usuario: str, mensaje: str) -> str:
    """El contratista carga franjas de disponibilidad para la visita."""
    from models.visita import Visita
    from services import coordinacion_visita

    conv = _conversaciones[usuario]
    visita = db.get(Visita, conv["visita_id"])
    if visita is None:
        del _conversaciones[usuario]
        return "⚠️ No encontré la visita a coordinar. Escribí *ayuda* para ver los comandos."

    texto = mensaje.strip()

    if _es_comando(texto, "listo", "terminar", "fin", "ok"):
        ok, motivo = coordinacion_visita.finalizar_disponibilidad(db, visita)
        if ok:
            del _conversaciones[usuario]
            return (
                "✅ ¡Gracias! Le pasé tus opciones a quien creó el reclamo. "
                "Te aviso apenas elija un horario."
            )
        f1, _ = coordinacion_visita.ejemplo_formato_fecha()
        if motivo == "todas_pasadas":
            return (
                "⚠️ Las opciones que habías cargado ya pasaron.\n"
                f"Por favor ingresá al menos una opción con fecha y hora posterior a la actual (ej: _{f1}_)."
            )
        return (
            "⚠️ Todavía no cargaste ninguna opción válida.\n"
            f"Enviá al menos una en formato *DD/MM HH:MM* (ej: _{f1}_)."
        )

    # Validar el formato DD/MM HH:MM para poder programar recordatorios.
    if not coordinacion_visita.formato_valido(texto):
        f1, _ = coordinacion_visita.ejemplo_formato_fecha()
        return (
            "⚠️ No pude interpretar esa fecha. Usá el formato *DD/MM HH:MM*.\n"
            f"Por ejemplo: _{f1}_\n\n"
            "Podés mandar varias juntas separadas por coma o en mensajes distintos."
        )

    # Validar que no se ingresen fechas anteriores a la actual
    pasadas = coordinacion_visita.opciones_pasadas(texto)
    if pasadas:
        f1, _ = coordinacion_visita.ejemplo_formato_fecha()
        if len(pasadas) == 1:
            return (
                f"⚠️ La fecha y hora ingresada (*{pasadas[0]}*) ya pasó.\n\n"
                "No podés coordinar visitas en fechas pasadas. "
                f"Por favor ingresá una fecha y hora posterior a la actual (ej: _{f1}_)."
            )
        pasadas_str = ", ".join(f"*{p}*" for p in pasadas)
        return (
            f"⚠️ Las siguientes fechas ya pasaron: {pasadas_str}.\n\n"
            f"Todas las opciones deben ser posteriores a la fecha y hora actual (ej: _{f1}_)."
        )

    cantidad = coordinacion_visita.agregar_disponibilidad(db, visita, texto)
    palabra = "opción" if cantidad == 1 else "opciones"
    return (
        f"🗓️ Anoté {cantidad} {palabra}. Podés seguir cargando más "
        "o escribí *listo* cuando termines."
    )


def _procesar_visita_eleccion(db: Session, usuario: str, mensaje: str) -> str:
    """El creador del reclamo elige uno de los horarios propuestos."""
    from models.contratista import Contratista
    from models.reclamo import Reclamo
    from models.visita import EstadoVisita, Visita
    from services import coordinacion_visita

    conv = _conversaciones[usuario]
    visita = db.get(Visita, conv["visita_id"])
    if visita is None:
        del _conversaciones[usuario]
        return "⚠️ No encontré la visita a coordinar. Escribí *ayuda* para ver los comandos."

    texto = mensaje.strip().replace("#", "")
    try:
        indice = int(texto)
    except ValueError:
        return "⚠️ Respondé con el número de la opción que preferís (ej: *1*)."

    try:
        elegido = coordinacion_visita.confirmar_eleccion(db, visita, indice)
    except coordinacion_visita.FechaPasada:
        # La opción elegida ya venció. Ver si quedan otras opciones futuras.
        opciones = coordinacion_visita._opciones_lista(visita)
        ahora = reloj.ahora()
        opciones_futuras = [
            (i + 1, op) for i, op in enumerate(opciones)
            if (dt := coordinacion_visita._parsear_fecha(op)) is not None and dt > ahora
        ]

        if opciones_futuras:
            lineas = "\n".join(f"{num}. {op}" for num, op in opciones_futuras)
            opcion_rechazada = opciones[indice - 1] if 0 <= indice - 1 < len(opciones) else ""
            return (
                f"⚠️ El horario seleccionado (*{opcion_rechazada}*) ya pasó y no se puede coordinar.\n\n"
                f"Por favor elegí una de las opciones que siguen vigentes:\n\n{lineas}\n\n"
                "Respondé con el número de la opción elegida."
            )

        # Si todas las opciones de la visita ya pasaron, se le pide nueva disponibilidad al contratista
        del _conversaciones[usuario]
        visita.estado = EstadoVisita.ESPERANDO_DISPONIBILIDAD
        visita.disponibilidades = None
        db.commit()

        reclamo = db.get(Reclamo, visita.reclamo_id)
        contratista = db.get(Contratista, visita.contratista_id) if reclamo else None
        if contratista and contratista.telefono:
            registrar_estado_conversacion(
                contratista.telefono,
                {"paso": "visita_disponibilidad", "visita_id": visita.id},
            )
            f1, _ = coordinacion_visita.ejemplo_formato_fecha()
            coordinacion_visita._enviar(
                contratista.telefono,
                f"📅 *Reclamo #{reclamo.id} — {reclamo.nombre_escuela}*\n\n"
                "Los horarios que habías propuesto para la visita ya pasaron sin haber sido confirmados.\n\n"
                f"Por favor indicá nuevas opciones de disponibilidad con fecha y hora posterior a la actual "
                f"(ej: _{f1}_).\n"
                "Cuando termines, escribí *listo*.",
            )

        return (
            "⚠️ Todos los horarios propuestos por el contratista ya pasaron sin confirmación.\n\n"
            "Le solicitamos al contratista que nos envíe nuevas opciones de disponibilidad. "
            "Te avisaremos por acá apenas las recibamos."
        )

    if elegido is None:
        return "⚠️ Ese número no corresponde a ninguna opción. Probá de nuevo."

    del _conversaciones[usuario]
    return (
        f"✅ ¡Listo! Confirmé la visita para:\n*{elegido}*\n\n"
        "El contratista fue notificado. Les vamos a recordar la visita el día "
        "anterior y el mismo día."
    )


def _procesar_avance_ejecucion(db: Session, usuario: str, mensaje: str) -> str:
    """El contratista manda avance (texto) o reporta que terminó. No cierra el reclamo."""
    from services import avance_contratista

    conv = _conversaciones[usuario]
    reclamo = db.get(Reclamo, conv["reclamo_id"])
    if reclamo is None:
        del _conversaciones[usuario]
        return "⚠️ No encontré el reclamo. Escribí *ayuda* para ver los comandos."

    hallado = avance_contratista.reclamo_en_ejecucion_de(db, usuario)
    contratista = hallado[1] if hallado else None
    texto = mensaje.strip()
    norma = _normalizar_comando(texto)

    if _es_reporte_termino(texto):
        fila = (
            db.query(RecordatorioContratista)
            .filter(RecordatorioContratista.reclamo_id == reclamo.id)
            .first()
        )
        if fila and fila.consulto_escuela:
            del _conversaciones[usuario]
            return (
                f"👍 Ya tenemos registrado que terminaste el reclamo #{reclamo.id}.\n"
                "Estamos esperando la confirmación de la escuela para darlo por finalizado."
            )
        from services import seguimiento

        avance_contratista.registrar_avance_texto(
            db, reclamo, contratista, texto, termino=True
        )
        seguimiento.preguntar_a_escuela_si_resuelto(db, reclamo, registrar_comentario=False)
        del _conversaciones[usuario]
        return (
            f"✅ ¡Gracias! Registré que el trabajo del reclamo #{reclamo.id} está *terminado*.\n"
            "Le pedimos a la escuela que confirme que quedó resuelto para cerrarlo."
        )

    if _es_comando_listo(texto) or norma in ("listo",):
        del _conversaciones[usuario]
        return (
            "👍 Quedó registrado lo que mandaste.\n"
            "Si hay más avance, escribí cuando te pidamos novedades o mandá *terminé* "
            "si el trabajo ya está listo."
        )

    if len(texto) < 2:
        return "⚠️ Contame el avance (porcentaje, qué hiciste) o mandá una foto."

    avance_contratista.registrar_avance_texto(db, reclamo, contratista, texto)
    return (
        f"📝 Anoté el avance en el reclamo #{reclamo.id}.\n"
        "Podés seguir mandando texto o fotos. Cuando termines el trabajo, escribí *terminé*."
    )


def _procesar_cu05_inicio(db: Session, usuario: str, mensaje: str) -> str:
    """CU-05 pieza 1: respuesta del contratista a '¿pudiste empezar?' (en la fecha pactada)."""
    from services import coordinacion_visita

    conv = _conversaciones[usuario]
    reclamo = db.get(Reclamo, conv.get("reclamo_id"))
    if reclamo is None or reclamo.estado != EstadoReclamo.VISITA_COORDINADA:
        del _conversaciones[usuario]
        return "⚠️ Ese reclamo ya no está esperando el inicio. Escribí *ayuda* para ver opciones."

    if _es_confirmacion_no(mensaje):
        from models.visita import Visita

        visita = db.get(Visita, conv.get("visita_id"))
        if visita is not None:
            coordinacion_visita.reprogramar_visita(db, visita)
        # reprogramar_visita deja al contratista en el paso de disponibilidad.
        return (
            "Entendido, reprogramemos. Mandame tu nueva disponibilidad en formato "
            "*DD/MM HH:MM* y escribí *listo* cuando termines."
        )

    if _es_confirmacion_si(mensaje):
        hallado = coordinacion_visita.contratista_de_reclamo_coordinado(db, usuario)
        contratista = hallado[1] if hallado else None
        coordinacion_visita.registrar_inicio_obra(db, reclamo, contratista)
        del _conversaciones[usuario]
        return (
            f"🛠️ ¡Genial! El reclamo #{reclamo.id} quedó *en ejecución*.\n\n"
            "Te vamos a consultar mañana a esta misma hora para ver cómo viene el trabajo.\n\n"
            "Si terminás antes, podés avisarnos directamente por acá enviando un mensaje que diga *terminé* o *listo* para confirmar que el trabajo está terminado."
        )

    return (
        "Respondé con el botón, o escribí *sí* si pudiste empezar, o *no* si no pudiste."
    )


def _procesar_cu05_termino(db: Session, usuario: str, mensaje: str) -> str:
    """CU-05 pieza 2: respuesta del contratista a '¿terminaste?'."""
    from services import avance_contratista, seguimiento

    conv = _conversaciones[usuario]
    reclamo = db.get(Reclamo, conv.get("reclamo_id"))
    if reclamo is None or reclamo.estado != EstadoReclamo.EN_EJECUCION:
        del _conversaciones[usuario]
        return "⚠️ Ese reclamo ya no está en ejecución. Escribí *ayuda* para ver opciones."

    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila and fila.consulto_escuela:
        del _conversaciones[usuario]
        return (
            f"👍 Ya tenemos registrado que terminaste el reclamo #{reclamo.id}.\n"
            "Estamos esperando la confirmación de la escuela para darlo por finalizado."
        )

    # En el porcentaje todavía puede decir que sí terminó; en la descripción no se mira,
    # porque frases como "terminé la parte eléctrica" son avance, no término.
    if conv.get("paso") in PASOS_REPORTE_AVANCE and not (
        conv["paso"] == "cu05_porcentaje" and _es_reporte_termino(mensaje)
    ):
        return _procesar_cu05_reporte_avance(db, usuario, reclamo, mensaje)

    # Esperando el tiempo estimado: salvo que diga explícitamente que sí terminó, se toma
    # el texto como el estimado restante.
    if conv.get("paso") == "cu05_estimado" and not (_es_confirmacion_si(mensaje) or _es_reporte_termino(mensaje)):
        seguimiento.registrar_tiempo_estimado(db, reclamo, mensaje)
        del _conversaciones[usuario]
        return (
            f"👍 Anotado. Te vuelvo a consultar en {seguimiento.seguimiento_horas():g} horas "
            "para ver cómo viene. Si terminás antes, avisame por acá."
        )

    if _es_confirmacion_si(mensaje) or _es_reporte_termino(mensaje):
        hallado = avance_contratista.reclamo_en_ejecucion_de(db, usuario)
        contratista = hallado[1] if hallado else None
        avance_contratista.registrar_avance_texto(
            db, reclamo, contratista, mensaje, termino=True
        )
        seguimiento.preguntar_a_escuela_si_resuelto(db, reclamo, registrar_comentario=False)
        del _conversaciones[usuario]
        return (
            f"✅ ¡Gracias! Registré que el trabajo del reclamo #{reclamo.id} está *terminado*.\n"
            "Le pedimos a la escuela que confirme que quedó resuelto para cerrarlo."
        )

    if _es_confirmacion_no(mensaje):
        # Antes del estimado se pide un reporte: porcentaje, descripción y fotos/videos (opcional).
        conv["paso"] = "cu05_porcentaje"
        conv["media_avance"] = 0
        return (
            "Dale. Antes de seguir necesito un breve reporte del avance.\n\n"
            "📊 *1/3:* ¿Qué porcentaje del trabajo tenés hecho? (ej: *40%*)"
        )

    # Texto libre que no es sí/no ni término: lo tratamos como un avance normal y re-preguntamos.
    hallado = avance_contratista.reclamo_en_ejecucion_de(db, usuario)
    contratista = hallado[1] if hallado else None
    avance_contratista.registrar_avance_texto(db, reclamo, contratista, mensaje)
    return (
        "📝 Anoté el avance. ¿Terminaste el trabajo? Respondé *sí* o *no*."
    )


# CU-05: el contratista respondió que todavía no terminó. Se le pide el porcentaje de
# avance, una descripción breve y, opcionalmente, fotos/videos; después sigue la pregunta
# del estimado.
PASOS_REPORTE_AVANCE = ("cu05_porcentaje", "cu05_descripcion", "cu05_fotos")


def _porcentaje_avance(texto: str) -> int | None:
    m = re.search(r"\d{1,3}", texto or "")
    if not m:
        return None
    valor = int(m.group(0))
    return valor if 0 <= valor <= 100 else None


def _procesar_cu05_reporte_avance(db: Session, usuario: str, reclamo: Reclamo, mensaje: str) -> str:
    from services import avance_contratista

    conv = _conversaciones[usuario]
    texto = (mensaje or "").strip()

    if conv["paso"] == "cu05_porcentaje":
        porcentaje = _porcentaje_avance(texto)
        if porcentaje is None:
            return "⚠️ Decime un número del 0 al 100. Por ejemplo: *40%*."
        if porcentaje == 100:
            return (
                "Si el trabajo ya está al 100%, escribí *terminé*. "
                "Si no, decime el porcentaje que llevás hecho."
            )
        conv["porcentaje"] = porcentaje
        conv["paso"] = "cu05_descripcion"
        return "📝 *2/3:* Contame brevemente en qué etapa está el trabajo."

    if conv["paso"] == "cu05_descripcion":
        if len(texto) < 10:
            return "⚠️ Contame un poco más (mínimo 10 caracteres) en qué etapa está el trabajo."
        conv["descripcion"] = texto
        conv["paso"] = "cu05_fotos"
        return (
            "📷 *3/3 (opcional):* Si querés, mandame fotos o videos del trabajo realizado "
            "hasta ahora y escribí *listo* cuando termines.\n"
            "Si no tenés, escribí *omitir*."
        )

    # cu05_fotos: opcional, se cierra con "listo" o "omitir".
    if not (_es_comando_listo(texto) or _es_comando(texto, "omitir", "saltar", "no tengo", "no")):
        return "📷 Mandame fotos o videos y escribí *listo*, o escribí *omitir* para seguir sin fotos."
    hallado = avance_contratista.reclamo_en_ejecucion_de(db, usuario)
    contratista = hallado[1] if hallado else None
    avance_contratista.registrar_reporte_avance(
        db,
        reclamo,
        contratista,
        porcentaje=conv["porcentaje"],
        descripcion=conv["descripcion"],
        cantidad_media=conv.get("media_avance", 0),
    )
    _conversaciones[usuario] = {"paso": "cu05_estimado", "reclamo_id": reclamo.id}
    return (
        f"✅ Gracias, registré el avance del reclamo #{reclamo.id}.\n\n"
        "¿Cuánto tiempo estimás que te falta para terminar?\n"
        "Por ejemplo: *2 días*, *5 horas*."
    )


def _procesar_cu05_resuelto(db: Session, usuario: str, mensaje: str) -> str:
    """CU-05 pieza 3: respuesta de la escuela a '¿quedó resuelto?'."""
    from services import resolucion_escuela, seguimiento

    conv = _conversaciones[usuario]
    reclamo = db.get(Reclamo, conv.get("reclamo_id"))
    if reclamo is None or reclamo.estado != EstadoReclamo.EN_EJECUCION:
        del _conversaciones[usuario]
        return "⚠️ Ese reclamo ya no está en ejecución. Escribí *ayuda* para ver opciones."

    if _es_confirmacion_si(mensaje):
        resolucion_escuela.registrar_resolucion(db, reclamo)
        del _conversaciones[usuario]
        return (
            f"✅ ¡Gracias! El reclamo #{reclamo.id} quedó *finalizado*.\n"
            "Si el problema vuelve a aparecer, podés cargar un nuevo reclamo cuando quieras."
        )

    if _es_confirmacion_no(mensaje):
        seguimiento.reactivar_seguimiento(db, reclamo)
        db.commit()
        del _conversaciones[usuario]
        return (
            "Entendido, lo dejamos en ejecución y seguimos el trabajo con el contratista. "
            "Te volveremos a consultar."
        )

    return "Respondé con el botón, o escribí *sí* si quedó resuelto, o *no* si todavía no."


def _reconstruir_cu05(db: Session, usuario: str, mensaje: str) -> str | None:
    """Reconstruye el paso de seguimiento CU-05 desde la base si se perdió en memoria o reporte proactivo."""
    from services import cu05_botones, coordinacion_visita, resolucion_escuela

    raw = (mensaje or "").strip()
    es_boton = raw in cu05_botones.TODOS
    es_si_no = _es_confirmacion_si(mensaje) or _es_confirmacion_no(mensaje)
    es_termino = _es_reporte_termino(mensaje)
    if not (es_boton or es_si_no or es_termino):
        return None

    # Botón de inicio o un sí/no mientras hay una visita coordinada con pregunta enviada.
    if raw in (cu05_botones.INICIO_SI, cu05_botones.INICIO_NO) or (es_si_no and not es_termino):
        hallado = coordinacion_visita.contratista_de_reclamo_coordinado(db, usuario)
        if hallado is not None:
            from models.visita import EstadoVisita, Visita

            reclamo_c, _contratista = hallado
            visita = (
                db.query(Visita)
                .filter(
                    Visita.reclamo_id == reclamo_c.id,
                    Visita.estado == EstadoVisita.CONFIRMADA,
                    Visita.pregunta_inicio_enviada.isnot(None),
                )
                .order_by(Visita.id.desc())
                .first()
            )
            if visita is not None:
                _conversaciones[usuario] = {
                    "paso": "cu05_inicio",
                    "visita_id": visita.id,
                    "reclamo_id": reclamo_c.id,
                }
                return _procesar_cu05_inicio(db, usuario, mensaje)

    # Botón de resuelto (escuela) o sí/no de la escuela creadora de un reclamo en ejecución.
    if raw in (cu05_botones.RESUELTO_SI, cu05_botones.RESUELTO_NO) or (es_si_no and not es_termino):
        reclamo_r = resolucion_escuela.reclamo_en_ejecucion_del_creador(db, usuario)
        if reclamo_r is not None:
            _conversaciones[usuario] = {"paso": "cu05_resuelto", "reclamo_id": reclamo_r.id}
            return _procesar_cu05_resuelto(db, usuario, mensaje)

    # Botón de terminó (contratista), sí/no, o reporte proactivo de término del contratista de un reclamo en ejecución.
    if raw in (cu05_botones.TERMINO_SI, cu05_botones.TERMINO_NO) or es_si_no or es_termino:
        from services import avance_contratista

        hallado = avance_contratista.reclamo_en_ejecucion_de(db, usuario)
        if hallado is not None:
            reclamo_t, _contratista = hallado
            _conversaciones[usuario] = {"paso": "cu05_termino", "reclamo_id": reclamo_t.id}
            return _procesar_cu05_termino(db, usuario, mensaje)

    return None


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

    from services.conversaciones import activa as conv_activa
    from services.conversaciones import cancelar_por_usuario
    from services.conversaciones import pedir_operador, pedir_volver_bot, solicitar as solicitar_operador

    conv_hum = conv_activa(db, usuario) if usuario else None
    if conv_hum is not None:
        esperando = conv_hum.estado.value == "ESPERANDO_OPERADOR"
        if pedir_volver_bot(texto, en_espera=esperando):
            cancelar_por_usuario(db, conv_hum.id)
            menu = _mostrar_ayuda(variante="menu")
            menu = {
                **menu,
                "body": (
                    "👌 Listo, volviste con el asistente.\n\n" + (menu.get("body") or "")
                ).strip(),
            }
            return menu
        return ""

    # Evaluar si es una sesión nueva ANTES de registrar esta interacción.
    sesion_nueva = _es_sesion_nueva(usuario)
    tenia_actividad = bool(usuario) and usuario in _ultima_actividad
    if usuario:
        _ultima_actividad[usuario] = datetime.now(timezone.utc)

    # Cancelar siempre funciona
    if texto == "cancelar" and usuario in _conversaciones:
        del _conversaciones[usuario]
        return "❌ Operación cancelada. Escribí *ayuda* para ver los comandos."

    if usuario and pedir_operador(texto):
        from services.configuracion_atencion import dentro_de_atencion, mensaje_fuera_horario

        if not dentro_de_atencion(db):
            return mensaje_fuera_horario(db)
        solicitar_operador(db, usuario)
        _conversaciones.pop(usuario, None)
        return {
            "tipo": "botones",
            "body": (
                "🙋 Te estoy pasando con un operador. En breve te van a responder.\n"
                "Mientras tanto podés seguir escribiendo acá.\n\n"
                "Si tardamos, tocá *Volver al bot* o escribí *cancelar*."
            ),
            "botones": [{"id": "cancelar", "title": "Volver al bot"}],
        }

    # Si el creador está aportando información adicional a un reclamo
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "info_adicional":
        return _procesar_info_adicional(db, usuario, mensaje)

    # Si el usuario está esperando ingresar un ID para buscar un reclamo
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "buscar_id":
        return _procesar_buscar_id(db, usuario, mensaje)

    # Si pasó más de una hora y ya no hay recordatorio pendiente, no seguir en avances.
    if (
        sesion_nueva
        and tenia_actividad
        and usuario in _conversaciones
        and _conversaciones[usuario].get("paso") == "avance_ejecucion"
        and avance_contratista.estado_conversacion_avance(db, usuario) is None
    ):
        del _conversaciones[usuario]

    # Coordinación de visita: contratista cargando disponibilidad
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "visita_disponibilidad":
        visita_id = _conversaciones[usuario].get("visita_id")
        visita = db.get(Visita, visita_id) if visita_id else None
        reclamo_visita = db.get(Reclamo, visita.reclamo_id) if visita else None
        if reclamo_visita and reclamo_visita.estado == EstadoReclamo.EN_EJECUCION:
            _conversaciones[usuario] = {
                "paso": "avance_ejecucion",
                "reclamo_id": reclamo_visita.id,
            }
            return _procesar_avance_ejecucion(db, usuario, mensaje)
        return _procesar_visita_disponibilidad(db, usuario, mensaje)

    # Coordinación de visita: creador eligiendo un horario
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "visita_eleccion":
        return _procesar_visita_eleccion(db, usuario, mensaje)

    # CU-05 pieza 1: contratista responde si pudo empezar la obra
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "cu05_inicio":
        return _procesar_cu05_inicio(db, usuario, mensaje)

    # CU-05 pieza 2: contratista responde si terminó (o informa tiempo estimado)
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") in (
        "cu05_termino", "cu05_estimado", *PASOS_REPORTE_AVANCE
    ):
        return _procesar_cu05_termino(db, usuario, mensaje)

    # CU-05 pieza 3: escuela confirma si el problema quedó resuelto
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "cu05_resuelto":
        return _procesar_cu05_resuelto(db, usuario, mensaje)

    # Avance de obra: respuesta al recordatorio (paso en memoria o reconstruido)
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "avance_ejecucion":
        if texto in (
            "ayuda",
            "help",
            "menu",
            "menú",
            "inicio",
            "hola",
            "hi",
            "nuevo",
            "crear",
            "cargar",
            "nuevo reclamo",
            "libre",
        ):
            del _conversaciones[usuario]
        else:
            return _procesar_avance_ejecucion(db, usuario, mensaje)

    # CU-05: si el usuario responde a una pregunta de seguimiento pero el estado en memoria
    # se perdió (reinicio del backend), reconstruirlo desde la base según el estado real.
    if usuario not in _conversaciones:
        reconstruido = _reconstruir_cu05(db, usuario, mensaje)
        if reconstruido is not None:
            return reconstruido

    # Si no hay estado en memoria (ej. el backend se reinició), reconstruirlo desde la
    # base para no perder una coordinación de visita en curso.
    if usuario not in _conversaciones:
        from services.avance_contratista import estado_conversacion_avance
        from services.coordinacion_visita import estado_conversacion_pendiente

        estado_db = estado_conversacion_pendiente(db, usuario)
        if estado_db is None:
            estado_db = estado_conversacion_avance(db, usuario)
        if estado_db is not None:
            _conversaciones[usuario] = estado_db
            if estado_db["paso"] == "visita_disponibilidad":
                return _procesar_visita_disponibilidad(db, usuario, mensaje)
            if estado_db["paso"] == "visita_eleccion":
                return _procesar_visita_eleccion(db, usuario, mensaje)
            if estado_db["paso"] == "avance_ejecucion":
                return _procesar_avance_ejecucion(db, usuario, mensaje)

    # Si el usuario está en medio de una conversación de creación
    if usuario in _conversaciones:
        return _procesar_creacion(db, usuario, mensaje)

    # Primer mensaje que ya cuenta un problema → no mostrar el menú de bienvenida.
    if ai_config.ai_whatsapp_enabled() and _parece_descripcion_reclamo(mensaje):
        _iniciar_libre(usuario)
        cuerpo = _sin_saludo_inicial(mensaje) or mensaje
        return _procesar_creacion(db, usuario, cuerpo)

    # Comando: nuevo reclamo
    if texto in ("nuevo", "crear", "cargar", "nuevo reclamo"):
        return _iniciar_creacion(usuario)

    # Comando: modo conversacional IA (opt-in)
    if texto in ("libre", "contame el problema", "modo ia"):
        if not ai_config.ai_whatsapp_enabled():
            return (
                "⚠️ El modo asistido por IA no está habilitado.\n"
                "Escribí *nuevo* para cargar un reclamo paso a paso."
            )
        return _iniciar_libre(usuario)

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
            "• *operador* — Hablar con una persona\n"
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

    from services.conversaciones import activa as conv_activa

    if usuario and conv_activa(db, usuario) is not None:
        return ""

    # Reporte de avance pedido tras "todavía no terminé": las fotos/videos van al reclamo.
    if usuario in _conversaciones and _conversaciones[usuario].get("paso") in PASOS_REPORTE_AVANCE:
        conv = _conversaciones[usuario]
        reclamo = db.get(Reclamo, conv.get("reclamo_id"))
        if reclamo is None:
            del _conversaciones[usuario]
            return "⚠️ No encontré el reclamo. Escribí *ayuda* para ver los comandos."
        avance_contratista.registrar_avance_media(db, reclamo, url_local, mime_type)
        conv["media_avance"] = conv.get("media_avance", 0) + 1
        tipo_str = "📹 Video" if "video" in (mime_type or "") else "📷 Foto"
        if conv["paso"] == "cu05_fotos":
            return (
                f"{tipo_str} recibida ✅ (total: {conv['media_avance']})\n"
                "Podés seguir enviando o escribí *listo* para continuar."
            )
        return f"{tipo_str} recibida ✅. La guardé en el reclamo; seguí con el paso actual."

    if usuario not in _conversaciones or _conversaciones[usuario].get("paso") != "avance_ejecucion":
        estado_av = avance_contratista.estado_conversacion_avance(db, usuario)
        if estado_av is not None:
            _conversaciones[usuario] = estado_av

    if usuario in _conversaciones and _conversaciones[usuario].get("paso") == "avance_ejecucion":
        conv = _conversaciones[usuario]
        reclamo = db.get(Reclamo, conv["reclamo_id"])
        if reclamo is None:
            del _conversaciones[usuario]
            return "⚠️ No encontré el reclamo. Escribí *ayuda* para ver los comandos."
        avance_contratista.registrar_avance_media(db, reclamo, url_local, mime_type)
        tipo_str = "📹 Video" if "video" in (mime_type or "") else "📷 Foto"
        return (
            f"{tipo_str} de avance en el reclamo #{reclamo.id} ✅\n"
            "Podés seguir enviando o, si el trabajo ya está listo, escribí *terminé*."
        )

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
        if paso in ("libre", "escuela", "ubicacion", "descripcion", "faltantes", "media", "confirmacion"):
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


def procesar_audio(
    db: Session,
    usuario: str,
    audio: bytes,
    mime_type: str,
    proveedor_stt: str | None = None,
):
    """Transcribe una nota de voz y la procesa como si fuera texto."""
    _texto, _proveedor, respuesta = procesar_audio_detalle(
        db, usuario, audio, mime_type, proveedor_stt=proveedor_stt
    )
    return respuesta


def procesar_audio_detalle(
    db: Session,
    usuario: str,
    audio: bytes,
    mime_type: str,
    proveedor_stt: str | None = None,
) -> tuple[str | None, str, object]:
    """Como procesar_audio, pero también devuelve (transcripcion, proveedor, respuesta)."""
    from services.conversaciones import activa as conv_activa

    proveedor = ai_config.resolver_stt_provider(proveedor_stt)
    if usuario and conv_activa(db, usuario) is not None:
        return None, proveedor, ""

    try:
        texto = stt.transcribir_audio(audio, mime_type, proveedor=proveedor)
    except stt.TranscripcionError:
        return None, proveedor, "⚠️ No pude transcribir el audio. Probá escribir el mensaje."

    try:
        registro.registrar(
            db,
            tipo=TipoRecomendacionIA.STT,
            payload={"transcripcion": texto, "mime_type": mime_type},
            proveedor=proveedor,
        )
        db.commit()
    except Exception:
        logger.exception("No se pudo persistir la transcripción STT")
        db.rollback()

    # El audio entra como texto: menú si es el primer mensaje, reclamo solo si
    # ya eligió *nuevo* / modo IA o si el transcript es ese comando.
    return texto, proveedor, procesar_mensaje(db, texto, usuario)
