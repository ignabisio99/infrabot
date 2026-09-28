"""Proveedor mock: respuestas determinísticas sin llamar a ninguna API."""

from __future__ import annotations

import json
import re
from typing import Any

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

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Electricidad", ("electric", "luz", "cable", "enchufe", "tablero", "corto", "toma")),
    ("Plomería", ("plomer", "agua", "canilla", "caño", "cañer", "inodor", "pérdida", "perdida", "cloaca", "grifo")),
    ("Gas", ("gas", "garrafa", "calefon", "calefón", "hornalla")),
    ("Techos", ("techo", "gotera", "chapas", "filtracion", "filtración", "cielo raso")),
    ("Pintura", ("pintura", "pintar", "pared descascar", "humedad mancha")),
    ("Pisos", ("piso", "baldosa", "cerámic", "ceramica", "vereda")),
    ("Aberturas", ("ventana", "puerta", "abertura", "vidrio", "cerradura", "persiana")),
    ("Infraestructura", ("pared", "muro", "column", "grieta", "estructura", "humedad")),
]

_URGENTE = (
    "urgente",
    "peligro",
    "riesgo",
    "incendio",
    "explos",
    "inund",
    "cortocircuito",
    "gas",
    "niño",
    "alumno",
    "evacu",
    "inmediato",
)

_BAJA = ("leve", "menor", "estético", "estetico", "cosmético", "cosmetico")


class MockProvider:
    name = "mock"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        hint = schema_hint or {}
        task = hint.get("task") or _infer_task(system, user)

        if task == "clasificacion":
            return _clasificar(user, hint)
        if task == "estimacion":
            return _estimar(user, hint)
        if task == "auditoria_notas":
            return {
                "notas_tecnicas": (
                    "Análisis mock: revisar ítems con mayor desvío y validar "
                    "cantidades contra la descripción del reclamo."
                ),
            }
        if task == "completitud":
            return _completitud(user)
        if task == "derivacion":
            return _derivacion(user)
        if task == "duplicados_semanticos":
            return _duplicados_semanticos(user)
        if task == "extraccion_reclamo":
            return _extraccion_reclamo(user)
        if task == "vision_reclamo":
            return {
                "hallazgos": ["Humedad visible en pared (mock)"],
                "severidad": "MEDIA",
                "sugerencia_descripcion": "Se observa humedad/deterioro en la superficie fotografiada.",
            }
        if task == "ocr_presupuesto":
            return {
                "items": [
                    {"descripcion": "Mano de obra", "cantidad": 4, "costo_unitario": 8000},
                    {"descripcion": "Materiales varios", "cantidad": 1, "costo_unitario": 45000},
                ]
            }
        return {k: v for k, v in hint.items() if k != "task"}

    def complete_json_with_images(
        self,
        *,
        system: str,
        user: str,
        images: list[bytes],
        mime_types: list[str] | None = None,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        hint = schema_hint or {}
        task = hint.get("task") or _infer_task(system, user)
        if task == "ocr_presupuesto":
            return self.complete_json(system=system, user=user, schema_hint={**hint, "task": "ocr_presupuesto"})
        return self.complete_json(
            system=system,
            user=user,
            schema_hint={**hint, "task": task if task != "unknown" else "vision_reclamo"},
        )


def _infer_task(system: str, user: str) -> str:
    blob = f"{system}\n{user}".lower()
    if "complet" in blob or "faltantes" in blob:
        return "completitud"
    if "derivar" in blob or "operador humano" in blob:
        return "derivacion"
    if "similitud_semantica" in blob or "candidatos:" in blob:
        return "duplicados_semanticos"
    if "mensaje del usuario" in blob or "texto libre" in blob:
        return "extraccion_reclamo"
    if "clasific" in blob or "categoría" in blob or "categoria" in blob:
        return "clasificacion"
    if "foto" in blob or "hallazgos" in blob or "vision" in blob:
        return "vision_reclamo"
    if "ítem" in blob or "item" in blob or "ocr" in blob or "extraé" in blob or "extrae" in blob:
        return "ocr_presupuesto"
    if "estim" in blob or "presupuesto preliminar" in blob:
        return "estimacion"
    if "audit" in blob or "desvío" in blob or "desvio" in blob:
        return "auditoria_notas"
    return "unknown"


def _derivacion(user: str) -> dict[str, Any]:
    """Mock de derivación con algo de contexto: keywords críticas salvo negación."""
    texto = user.lower()
    # Contextos donde una palabra crítica NO implica peligro activo.
    seguros = ("no hay riesgo", "sin riesgo", "ya cortaron", "ya cortó", "cortado",
               "el año pasado", "hace tiempo", "ya se solucion")
    if any(s in texto for s in seguros):
        return {
            "razonamiento": "Mock: menciona algo sensible pero el contexto indica que no hay peligro activo.",
            "derivar": False,
            "motivo": "Contexto sin peligro activo.",
        }
    for kw in ("gas", "incendio", "explos", "evacu", "peligro", "riesgo", "inund", "cortocircuito"):
        if kw in texto:
            return {
                "razonamiento": f"Mock: se detectó '{kw}' en un contexto que sugiere riesgo.",
                "derivar": True,
                "motivo": f"Posible situación crítica ('{kw}').",
            }
    return {
        "razonamiento": "Mock: no se detectaron señales de riesgo ni ambigüedad.",
        "derivar": False,
        "motivo": "Problema común sin urgencia.",
    }


def _completitud(user: str) -> dict[str, Any]:
    texto = user.lower()
    faltantes = []
    if "ubicación:" in texto or "ubicacion:" in texto:
        for line in user.splitlines():
            if line.lower().startswith("ubicaci"):
                valor = line.split(":", 1)[-1].strip()
                if len(valor) < 8 or valor.lower() in ("patio", "aula", "baño", "bano"):
                    faltantes.append(
                        {
                            "campo": "ubicacion",
                            "pregunta": "¿Podés precisar mejor la ubicación (piso, aula o sector)?",
                        }
                    )
    if "descripción:" in texto or "descripcion:" in texto:
        for line in user.splitlines():
            if line.lower().startswith("descripci"):
                valor = line.split(":", 1)[-1].strip()
                if len(valor) < 25:
                    faltantes.append(
                        {
                            "campo": "descripcion",
                            "pregunta": "¿Podés dar más detalle del problema (qué pasó y desde cuándo)?",
                        }
                    )
    return {
        "completo": len(faltantes) == 0,
        "faltantes": faltantes,
        "datos_extraidos": {},
    }


def _duplicados_semanticos(user: str) -> dict[str, Any]:
    scores = []
    for line in user.splitlines():
        if "id=" not in line:
            continue
        try:
            rid_part = line.split("id=", 1)[1]
            rid = int(rid_part.split()[0])
            sim = 0.6
            if "sim_jaccard=" in line:
                sim = float(line.split("sim_jaccard=", 1)[1].split(":")[0].strip())
            scores.append({"reclamo_id": rid, "similitud_semantica": sim})
        except (ValueError, IndexError):
            continue
    return {"scores": scores}


def _extraccion_reclamo(user: str) -> dict[str, Any]:
    """Extrae campos del mensaje libre con heurísticas determinísticas."""
    lineas = user.splitlines()
    texto = "\n".join(
        linea for linea in lineas if not linea.lower().startswith("mensaje del usuario")
    ).strip()

    escuela = None
    match = re.search(r"escuela\s+((?:\S+\s+){0,4}\S+)", texto, re.I)
    if match:
        # Cortar en palabras que claramente ya no son parte del nombre
        palabras = match.group(1).split()
        corte = len(palabras)
        for i, p in enumerate(palabras):
            if p.lower() in ("hay", "en", "el", "la", "de", "del", "con", "tiene", "se"):
                corte = i
                break
        nombre = " ".join(palabras[:corte]).strip()
        if nombre:
            escuela = f"Escuela {nombre}"

    ubicacion = None
    match = re.search(
        r"\b(baño|bano|aula|patio|pasillo|biblioteca|comedor|laboratorio|gimnasio)"
        r"([^,.;\n]*)",
        texto,
        re.I,
    )
    if match:
        ubicacion = match.group(0).strip()

    confianza = 0.6 if escuela else 0.3
    return {
        "nombre_escuela": escuela,
        "ubicacion": ubicacion,
        "descripcion": texto,
        "confianza": confianza,
    }


def _clasificar(user: str, hint: dict[str, Any]) -> dict[str, Any]:
    texto = user.lower()
    categoria = "Otro"
    for cat, keys in _KEYWORDS:
        if any(k in texto for k in keys):
            categoria = cat
            break

    if any(k in texto for k in _URGENTE):
        prioridad = "ALTA"
        confianza = 0.82
    elif any(k in texto for k in _BAJA) and categoria == "Pintura":
        prioridad = "BAJA"
        confianza = 0.75
    else:
        prioridad = "MEDIA"
        confianza = 0.7

    categorias = hint.get("categorias") or CATEGORIAS
    if categoria not in categorias:
        categoria = "Otro"

    return {
        "categoria": categoria,
        "prioridad": prioridad,
        "confianza": confianza,
        "razonamiento": f"Mock: detecté palabras clave que apuntan a {categoria}; prioridad {prioridad} según urgencia estimada.",
        "justificacion": f"Clasificación mock por palabras clave → {categoria}/{prioridad}.",
    }


def _estimar(user: str, hint: dict[str, Any]) -> dict[str, Any]:
    # Extrae categoría/prioridad del user message si vienen etiquetadas.
    cat_match = re.search(r"categor[ií]a:\s*([^\n]+)", user, re.I)
    pri_match = re.search(r"prioridad:\s*([^\n]+)", user, re.I)
    categoria = (cat_match.group(1).strip() if cat_match else "Otro")
    prioridad = (pri_match.group(1).strip().upper() if pri_match else "MEDIA")

    base = {
        "Electricidad": (80_000, 120_000, 15_000),
        "Plomería": (60_000, 100_000, 10_000),
        "Gas": (90_000, 140_000, 20_000),
        "Techos": (150_000, 200_000, 25_000),
        "Pintura": (40_000, 70_000, 8_000),
        "Pisos": (100_000, 130_000, 15_000),
        "Aberturas": (110_000, 90_000, 12_000),
        "Infraestructura": (200_000, 250_000, 30_000),
        "Otro": (50_000, 80_000, 10_000),
    }.get(categoria, (50_000, 80_000, 10_000))

    factor = {"ALTA": 1.25, "MEDIA": 1.0, "BAJA": 0.85}.get(prioridad, 1.0)
    materiales = round(base[0] * factor, 2)
    mano_obra = round(base[1] * factor, 2)
    otros = round(base[2] * factor, 2)
    total = round(materiales + mano_obra + otros, 2)

    confianza = 0.55 if categoria == "Otro" else 0.72
    if prioridad == "ALTA":
        confianza = max(0.4, confianza - 0.05)

    return {
        "materiales": materiales,
        "mano_obra": mano_obra,
        "otros": otros,
        "total": total,
        "confianza": confianza,
        "detalle": {
            "fuente": "mock_heuristicas",
            "categoria_usada": categoria,
            "prioridad_usada": prioridad,
            "nota": "Estimación preliminar mock. Reemplazar por LLM con históricos reales.",
        },
    }


def parse_user_payload(user: str) -> dict[str, Any]:
    """Intenta parsear un bloque JSON embebido en el mensaje de usuario."""
    try:
        start = user.index("{")
        end = user.rindex("}") + 1
        return json.loads(user[start:end])
    except (ValueError, json.JSONDecodeError):
        return {}
