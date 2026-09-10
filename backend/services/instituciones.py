"""Padrón de instituciones (escuelas): carga desde CSV y búsqueda tolerante.

Se usa al crear un reclamo para validar/sugerir la escuela que ingresa el usuario.
La búsqueda normaliza acentos y mayúsculas, y puntúa por cantidad de palabras del
texto que aparecen en el nombre o el domicilio de la institución.

El padrón se carga automáticamente al arrancar el backend (ver `cargar_padron_si_vacio`),
así que no hace falta correr scripts a mano.
"""

import csv
import logging
import os
import re
import unicodedata

from sqlalchemy.orm import Session

from models.institucion import Institucion

logger = logging.getLogger(__name__)

# CSV interno del sistema (recurso versionado dentro del backend).
_RUTA_PADRON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "instituciones.csv")


def importar_padron(db: Session, ruta_csv: str | None = None) -> tuple[int, int]:
    """Importa/actualiza el padrón desde un CSV. Devuelve (creadas, actualizadas).

    Idempotente: matchea por `Identificador`, así se puede volver a correr para
    actualizar datos o sumar escuelas nuevas sin duplicar.
    """
    ruta = ruta_csv or _RUTA_PADRON
    creados = 0
    actualizados = 0
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            identificador = (fila.get("Identificador") or "").strip() or None
            nombre = (fila.get("Nombre") or "").strip()
            if not nombre:
                continue

            datos = dict(
                identificador=identificador,
                nombre=nombre,
                domicilio=(fila.get("Domicilio") or "").strip() or None,
                localidad=(fila.get("Localidad") or "").strip() or None,
                codigo_postal=(fila.get("C. P.") or "").strip() or None,
            )

            existente = None
            if identificador:
                existente = (
                    db.query(Institucion)
                    .filter(Institucion.identificador == identificador)
                    .first()
                )

            if existente:
                for campo, valor in datos.items():
                    setattr(existente, campo, valor)
                actualizados += 1
            else:
                db.add(Institucion(**datos))
                creados += 1

    db.commit()
    return creados, actualizados


def cargar_padron_si_vacio(db: Session) -> None:
    """Carga el padrón desde el CSV interno solo si la tabla está vacía.

    Se llama al arrancar el backend. Si ya hay instituciones, no hace nada. Así el
    padrón está siempre disponible sin intervención manual, incluso tras un reset.
    """
    try:
        if db.query(Institucion.id).first() is not None:
            return
        if not os.path.exists(_RUTA_PADRON):
            logger.warning("Padrón de instituciones no encontrado en %s", _RUTA_PADRON)
            return
        creados, _ = importar_padron(db)
        logger.info("Padrón de instituciones cargado: %d escuelas.", creados)
    except Exception as exc:  # noqa: BLE001 - no romper el arranque por esto
        logger.warning("No se pudo cargar el padrón de instituciones: %s", exc)

# Palabras muy comunes que no ayudan a distinguir una escuela de otra.
_STOPWORDS = {
    "de", "la", "el", "los", "las", "del", "y", "e", "escuela", "colegio",
    "jardin", "instituto", "n", "nº", "no", "numero", "educacion", "educación",
    "primaria", "secundaria", "en", "a",
}


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin signos, para comparar de forma tolerante."""
    if not texto:
        return ""
    txt = unicodedata.normalize("NFKD", texto)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower()
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    # Separa letras pegadas a números para que "n14", "nº14" y "n 14" queden iguales
    # (el padrón tiene "Nº14" → "n 14"; el usuario suele escribir "n14").
    txt = re.sub(r"(?<=[a-z])(?=\d)", " ", txt)
    txt = re.sub(r"(?<=\d)(?=[a-z])", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _tokens(texto: str) -> set[str]:
    return {t for t in _normalizar(texto).split() if t and t not in _STOPWORDS}


def buscar_instituciones(db: Session, consulta: str, limite: int = 3) -> list[Institucion]:
    """Devuelve las instituciones que mejor coinciden con la consulta.

    Puntúa cada institución por cuántos tokens de la consulta aparecen en su nombre
    o domicilio. Devuelve las de mayor puntaje (con al menos una coincidencia).
    """
    tokens_consulta = _tokens(consulta)
    # Los números (ej. "45") pesan aunque sean cortos: identifican la escuela.
    numeros_consulta = {t for t in _normalizar(consulta).split() if t.isdigit()}
    tokens_consulta |= numeros_consulta

    if not tokens_consulta:
        return []

    instituciones = db.query(Institucion).all()
    puntuadas = []
    for inst in instituciones:
        texto_inst = _normalizar(f"{inst.nombre} {inst.domicilio or ''} {inst.localidad or ''}")
        tokens_inst = set(texto_inst.split())
        coincidencias = tokens_consulta & tokens_inst
        if not coincidencias:
            continue
        # Un número que coincide (ej. el número de escuela) suma más que una palabra.
        puntaje = sum(3 if t.isdigit() else 1 for t in coincidencias)
        puntuadas.append((puntaje, inst))

    puntuadas.sort(key=lambda x: x[0], reverse=True)
    return [inst for _, inst in puntuadas[:limite]]
