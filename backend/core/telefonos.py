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
