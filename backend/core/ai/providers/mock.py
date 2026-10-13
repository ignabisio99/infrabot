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
        if task == "resumen_reclamo":
            return _resumen_reclamo(user)
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

    def complete_with_tools(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        tool_ejecutores: dict[str, Any],
        schema_hint: dict[str, Any] | None = None,
        max_iteraciones: int = 5,
    ) -> dict[str, Any]:
        """Mock del agente: ejecuta TODAS las herramientas una vez (para simular que
        el agente las usó) y devuelve un análisis determinista con esos resultados."""
        pasos = []
        for nombre, ejecutor in tool_ejecutores.items():
            try:
                # Args mínimos deterministas a partir del texto del usuario.
                if nombre == "consultar_padron_escuela":
                    args = {"nombre": _campo(user, "Escuela")}
                elif nombre == "buscar_reclamos_similares":
                    args = {"nombre_escuela": _campo(user, "Escuela"), "descripcion": _campo(user, "Descripción")}
                else:
                    args = {"categoria": "Otro", "descripcion": _campo(user, "Descripción")}
                res = ejecutor(**args)
            except Exception:  # noqa: BLE001
                res = {"error": "mock"}
            pasos.append({"herramienta": nombre, "args": args, "resultado": res})

        base = _clasificar(user, schema_hint or {})
        return {
            "resultado": {
                "razonamiento": "Mock del agente: consulté padrón, similares y costos.",
                "categoria": base.get("categoria", "Otro"),
                "prioridad": base.get("prioridad", "MEDIA"),
                "escuela_en_padron": bool(
                    next((p["resultado"].get("encontrada") for p in pasos
                          if p["herramienta"] == "consultar_padron_escuela"), False)
                ),
                "es_posible_duplicado": any(
                    (p["resultado"].get("cantidad") or 0) > 0 for p in pasos
                    if p["herramienta"] == "buscar_reclamos_similares"
                ),
                "resumen_para_operador": "Análisis mock generado con herramientas.",
                "confianza": base.get("confianza", 0.7),
            },
            "pasos_agente": pasos,
        }

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


def _campo(texto: str, etiqueta: str) -> str:
    """Extrae el valor de una línea 'Etiqueta: valor' del user prompt (para el mock)."""
    for linea in texto.splitlines():
        if linea.strip().lower().startswith(etiqueta.lower() + ":"):
            return linea.split(":", 1)[1].strip()
    return ""


def _infer_task(system: str, user: str) -> str:
    blob = f"{system}\n{user}".lower()
    if "complet" in blob or "faltantes" in blob:
        return "completitud"
    if "derivar" in blob or "operador humano" in blob:
        return "derivacion"
    if "similitud_semantica" in blob or "candidatos:" in blob:
        return "duplicados_semanticos"
    if "muletillas" in blob or "notas de la conversación" in blob or "resumen del reclamo" in blob:
        return "resumen_reclamo"
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


def _resumen_reclamo(user: str) -> dict[str, Any]:
    cuerpo = user.split("Notas de la conversación:", 1)[-1].strip()
    utiles = []
    for linea in cuerpo.splitlines():
        t = linea.strip()
        if not t:
            continue
        bajo = t.lower()
        if bajo in ("ok", "si", "sí", "dale", "listo") or "flakito" in bajo or "ya te dije" in bajo:
            continue
        if t not in utiles:
            utiles.append(t)
    return {"descripcion": " ".join(utiles) or cuerpo}


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

    montos_hist = [
        float(m) for m in re.findall(r"monto_ajustado[=:]?\s*([0-9]+(?:\.[0-9]+)?)", user)
    ]
    if montos_hist:
        promedio = sum(montos_hist) / len(montos_hist)
        factor = {"ALTA": 1.08, "MEDIA": 1.0, "BAJA": 0.94}.get(prioridad, 1.0)
        total = round(promedio * factor, 2)
        materiales = round(total * 0.40, 2)
        mano_obra = round(total * 0.50, 2)
        otros = round(total - materiales - mano_obra, 2)
        confianza = 0.6 if categoria == "Otro" else 0.78
        fuente = "mock_historicos"
    else:
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
        fuente = "mock_heuristicas"

    if prioridad == "ALTA":
        confianza = max(0.4, confianza - 0.05)

    return {
        "materiales": materiales,
        "mano_obra": mano_obra,
        "otros": otros,
        "total": total,
        "confianza": confianza,
        "justificacion": (
            f"Estimación preliminar mock ({fuente}) para {categoria}/{prioridad}. "
            f"Total ${total:,.0f}: materiales ${materiales:,.0f}, "
            f"mano de obra ${mano_obra:,.0f} y otros ${otros:,.0f}."
        ),
        "detalle": {
            "fuente": fuente,
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
