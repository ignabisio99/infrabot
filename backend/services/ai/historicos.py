"""Búsqueda de costos históricos de referencia (tabla placeholder)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from models.referencia_costo import ReferenciaCosto
from services.ai import inflacion


# Sinónimos del dominio: cada grupo son formas de decir lo mismo. Al tokenizar, si
# aparece cualquiera, se agregan TODAS las del grupo. Así "el water rebalsa" y "el inodoro
# desborda" comparten tokens aunque usen palabras distintas. Agregar grupos acá es la
# forma barata de subir la fiabilidad ante redacciones diferentes del mismo problema.
_SINONIMOS: list[set[str]] = [
    {"inodoro", "water", "wáter", "vater", "váter", "retrete", "excusado", "sanitario"},
    {"desborda", "desborde", "rebalsa", "rebalse", "desbordar", "rebalsar", "derrama", "derrame"},
    {"tapado", "obstruido", "obstruccion", "atascado", "tapon", "taponado"},
    {"destapacion", "desobstruccion", "destapar", "desobstruir"},
    {"perdida", "fuga", "gotera", "filtracion", "goteo", "escape"},
    {"mochila", "deposito", "cisterna", "descarga"},
    {"canilla", "grifo", "griferia", "llave"},
    {"cañeria", "caño", "tuberia", "caño"},
    {"bacha", "pileta", "lavatorio", "lavabo"},
    {"pierde", "perdiendo", "chorrea", "sale", "saliendo"},
    {"baño", "sanitarios", "toilette"},
    {"roto", "rota", "rajado", "quebrado", "partido"},
    {"humedad", "mojado", "humedo", "inundacion", "inundado"},
]


def _quitar_acentos(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _tokens(texto: str) -> set[str]:
    # Se comparan sin acentos para que "cañería"/"caneria" o "baño"/"bano" coincidan.
    base = {t for t in re.findall(r"[a-záéíóúñü0-9]{3,}", texto.lower())}
    base = {_quitar_acentos(t) for t in base}
    # Expandir con sinónimos: si hay una palabra de un grupo, se suman todas las del grupo.
    expandido = set(base)
    for grupo in _SINONIMOS:
        grupo_sin = {_quitar_acentos(p) for p in grupo}
        if base & grupo_sin:
            expandido |= grupo_sin
    return expandido


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _cobertura(consulta: set[str], referencia: set[str]) -> float:
    """Fracción de las palabras de la referencia que aparecen en el reclamo.

    A diferencia de Jaccard, no penaliza que el reclamo sea largo: la descripción que
    redacta la IA tiene decenas de palabras ("inconveniente", "desperfecto", "normal
    funcionamiento", el nombre de la escuela...), y con Jaccard una referencia corta y
    muy relevante quedaba por debajo del umbral aunque compartiera lo importante
    (desborde, inodoro, varones, llave de paso). La cobertura mira cuánto de la
    referencia está contenido en el reclamo, que es lo que interesa para matchear."""
    if not consulta or not referencia:
        return 0.0
    return len(consulta & referencia) / len(referencia)


def _similitud(consulta: set[str], referencia: set[str]) -> float:
    """Similitud texto-reclamo: la mayor entre Jaccard y cobertura de la referencia."""
    return max(_jaccard(consulta, referencia), _cobertura(consulta, referencia))


@dataclass(frozen=True)
class ReferenciaAjustada:
    id: int
    categoria: str
    descripcion: str
    monto_original: Decimal
    monto_ajustado: Decimal
    similitud: float
    fecha_referencia: str
    meta_inflacion: dict


def buscar_referencias(
    db: Session,
    *,
    categoria: str,
    descripcion: str,
    limit: int = 5,
    umbral: float = 0.15,
) -> list[ReferenciaAjustada]:
    """Misma categoría y palabras en común; montos ajustados por IPC."""
    tokens_q = _tokens(descripcion)
    candidatos = (
        db.query(ReferenciaCosto)
        .filter(
            ReferenciaCosto.activo.is_(True),
            ReferenciaCosto.categoria.ilike(categoria.strip()),
        )
        .all()
    )
    # Si no hay en esa categoría, buscar en todas (menos estricto).
    if not candidatos:
        candidatos = db.query(ReferenciaCosto).filter(ReferenciaCosto.activo.is_(True)).all()

    resultados: list[ReferenciaAjustada] = []
    for ref in candidatos:
        # El plus por categoría no alcanza para entrar: si no hay palabras en común,
        # una fila genérica (por ejemplo un diagnóstico eléctrico en "Otro") se
        # pegaba a cualquier reclamo de esa categoría y la estimación copiaba ese texto.
        texto = _similitud(tokens_q, _tokens(ref.descripcion))
        if texto < umbral:
            continue
        sim = texto
        if categoria and ref.categoria.lower() == categoria.strip().lower():
            sim = min(1.0, sim + 0.15)
        monto_aj, meta = inflacion.ajustar_monto(db, Decimal(ref.monto_ars), ref.fecha_referencia)
        resultados.append(
            ReferenciaAjustada(
                id=ref.id,
                categoria=ref.categoria,
                descripcion=ref.descripcion,
                monto_original=Decimal(ref.monto_ars),
                monto_ajustado=monto_aj,
                similitud=round(sim, 3),
                fecha_referencia=ref.fecha_referencia.isoformat(),
                meta_inflacion=meta,
            )
        )

    resultados.sort(key=lambda r: (r.similitud, r.monto_ajustado), reverse=True)
    if resultados:
        return resultados[:limit]

    # Fallback: ninguna referencia superó el umbral de texto, pero el rubro SÍ tiene
    # históricos. En vez de caer al monto orientativo fijo (y mostrar "sin precedentes"),
    # se usan las referencias de la misma categoría como ancla. Se eligen las de monto
    # más típico (mediana) para no sesgar con los extremos caros o baratos del rubro.
    # El fallback solo aplica a rubros concretos con varios históricos: ahí sí el promedio
    # del rubro es un ancla legítima. No aplica a "Otro" (cajón de sastre) ni cuando hay
    # muy pocas referencias, donde anclar a una fila suelta sería adivinar.
    MINIMO_PARA_FALLBACK = 5
    if not categoria or categoria.strip().lower() == "otro":
        return []
    de_categoria = [
        r for r in candidatos if r.categoria.lower() == categoria.strip().lower()
    ]
    if len(de_categoria) < MINIMO_PARA_FALLBACK:
        return []

    de_categoria.sort(key=lambda r: Decimal(r.monto_ars))
    medio = len(de_categoria) // 2
    # Una ventana alrededor de la mediana: representa el costo típico del rubro.
    inicio = max(0, medio - limit // 2)
    representativas = de_categoria[inicio : inicio + limit]

    fallback: list[ReferenciaAjustada] = []
    for ref in representativas:
        monto_aj, meta = inflacion.ajustar_monto(db, Decimal(ref.monto_ars), ref.fecha_referencia)
        fallback.append(
            ReferenciaAjustada(
                id=ref.id,
                categoria=ref.categoria,
                descripcion=ref.descripcion,
                monto_original=Decimal(ref.monto_ars),
                monto_ajustado=monto_aj,
                # Similitud baja a propósito: hay ancla por rubro, no por coincidencia de
                # texto. Alcanza para no decir "sin precedentes" y dar un estimativo del rubro.
                similitud=0.2,
                fecha_referencia=ref.fecha_referencia.isoformat(),
                meta_inflacion=meta,
            )
        )
    return fallback


def confianza_por_precedentes(referencias: list[ReferenciaAjustada]) -> float:
    """Confianza heurística según cantidad y similitud de precedentes (CU-02)."""
    if not referencias:
        return 0.25
    n = len(referencias)
    avg_sim = sum(r.similitud for r in referencias) / n
    base = {1: 0.4, 2: 0.55, 3: 0.68}.get(n, 0.78)
    return round(min(0.92, base + avg_sim * 0.15), 3)
