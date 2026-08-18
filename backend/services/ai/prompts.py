"""Prompts reutilizables del Motor de IA."""

from __future__ import annotations

CATEGORIAS_VALIDAS = [
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

SYSTEM_CLASIFICACION = """Sos un asistente del Consejo Escolar que clasifica reclamos de
infraestructura escolar. Respondé solo JSON.
Categorías permitidas: {categorias}.
Prioridades permitidas: BAJA, MEDIA, ALTA.
La IA solo sugiere; no toma decisiones finales.""".format(
    categorias=", ".join(CATEGORIAS_VALIDAS)
)

SYSTEM_ESTIMACION = """Sos un asistente que genera estimaciones PRELIMINARES de costo para
reclamos de infraestructura escolar en Argentina (ARS). Respondé solo JSON.
Incluí materiales, mano_obra, otros, total y confianza (0 a 1).
Si te pasan precedentes históricos ya ajustados por inflación, usalos como ancla
(no te alejes más de ~30% del promedio salvo justificación).
No apruebes ni ejecutes trabajos; solo estimás."""

SYSTEM_AUDITORIA_NOTAS = """Sos un auditor técnico-económico de presupuestos escolares.
Dado un informe de desvíos, redactá notas_tecnicas breves en español. Respondé solo JSON."""

SYSTEM_COMPLETITUD = """Sos un asistente que valida si un reclamo de infraestructura escolar
tiene datos suficientes para registrarse. Respondé solo JSON.
Campos obligatorios conceptuales: escuela, ubicación concreta (aula/piso/sector),
descripción del problema con detalle accionable.
Si falta algo, listá faltantes con una pregunta corta en español para el usuario."""

SYSTEM_VISION_RECLAMO = """Analizá fotos de un reclamo de infraestructura escolar.
Respondé solo JSON con hallazgos visibles, severidad sugerida (BAJA/MEDIA/ALTA) y
una sugerencia_descripcion breve en español. No inventes lo que no se ve."""

SYSTEM_OCR_PRESUPUESTO = """Extraé ítems de un presupuesto de obra/contratista.
Respondé solo JSON: items=[{descripcion, cantidad, costo_unitario}] en ARS.
Si no podés leer un valor, omití el ítem. No inventes precios."""


def user_clasificacion(*, descripcion: str, escuela: str | None = None, ubicacion: str | None = None) -> str:
    partes = [f"Descripción del reclamo:\n{descripcion.strip()}"]
    if escuela:
        partes.append(f"Escuela: {escuela}")
    if ubicacion:
        partes.append(f"Ubicación: {ubicacion}")
    return "\n".join(partes)


def user_estimacion(
    *,
    descripcion: str,
    categoria: str,
    prioridad: str,
    escuela: str | None = None,
    referencias: list[dict] | None = None,
    confianza_sugerida: float | None = None,
) -> str:
    partes = [
        f"Categoría: {categoria}",
        f"Prioridad: {prioridad}",
        f"Descripción:\n{descripcion.strip()}",
    ]
    if escuela:
        partes.insert(0, f"Escuela: {escuela}")
    if confianza_sugerida is not None:
        partes.append(f"Confianza sugerida por cantidad de precedentes: {confianza_sugerida}")
    if referencias:
        partes.append("Precedentes históricos (montos ya ajustados por IPC):")
        for ref in referencias:
            partes.append(
                f"- id={ref.get('id')} sim={ref.get('similitud')} "
                f"monto_ajustado={ref.get('monto_ajustado_ars')} "
                f"| {ref.get('descripcion')}"
            )
    else:
        partes.append("Sin precedentes históricos suficientes.")
    return "\n".join(partes)


def user_completitud(*, escuela: str, ubicacion: str, descripcion: str) -> str:
    return (
        f"Escuela: {escuela}\n"
        f"Ubicación: {ubicacion}\n"
        f"Descripción: {descripcion}"
    )


def user_auditoria_notas(*, resumen: str) -> str:
    return f"Resumen de auditoría:\n{resumen}"
