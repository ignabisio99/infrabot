"""Normalización de teléfonos argentinos para registro, perfil y fichas."""

from __future__ import annotations

import re


def normalizar_telefono_ar(valor: str) -> str:
    """Devuelve el número con prefijo +54, sin espacios ni guiones.

    Si ya viene con +54 o 54, se unifica a +54. Si no, se antepone +54.
    """
    crudo = (valor or "").strip()
    if not crudo:
        return crudo
    # El simulador identifica la charla con el prefijo sim. Normalizarlo a +54
    # deja el reclamo con un número que no encuentra esos mensajes.
    if crudo.lower().startswith("sim"):
        return crudo

    tiene_mas = crudo.startswith("+")
    digitos = re.sub(r"\D", "", crudo)
    if not digitos:
        return crudo

    if digitos.startswith("54"):
        return f"+{digitos}"
    if tiene_mas:
        return f"+{digitos}"
    return f"+54{digitos}"


def clave_telefono(valor: str | None) -> str:
    """Los últimos 10 dígitos, que en Argentina son el número nacional: así 5491122334455,
    +54 9 11 2233-4455, 011 2233-4455 y sim5491122334455 son el mismo número."""
    return re.sub(r"\D", "", valor or "")[-10:]


def mismo_telefono(a: str | None, b: str | None) -> bool:
    clave = clave_telefono(a)
    return bool(clave) and clave == clave_telefono(b)


def filtro_mismo_telefono(columna, valor: str | None):
    """`mismo_telefono` como condición SQL sobre una columna de teléfono."""
    from sqlalchemy import false, func

    clave = clave_telefono(valor)
    if not clave:
        return false()
    return func.right(func.regexp_replace(columna, "[^0-9]", "", "g"), 10) == clave
