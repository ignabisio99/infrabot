"""Estimación preliminar de costos (CU-02 / RF04) con históricos + inflación."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from models.estimacion_preliminar import EstimacionPreliminar
from models.historial_estado_reclamo import OrigenCambioEstado
from models.reclamo import EstadoReclamo, Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import historicos, registro
from services.ai.contexto_reclamo import texto_para_ia
from services.ai.prompts import SYSTEM_ESTIMACION, user_estimacion
from services.estados_reclamo import TransicionInvalida, cambiar_estado

logger = logging.getLogger(__name__)

UMBRAL_DESVIO_ESTIMACION = Decimal("0.20")

_SCHEMA = {
    "task": "estimacion",
    "materiales": 0,
    "mano_obra": 0,
    "otros": 0,
    "total": 0,
    "confianza": 0.5,
    "justificacion": "",
    "detalle": {},
}


def generar_estimacion(
    db: Session,
    reclamo: Reclamo,
    *,
    transicionar: bool = True,
) -> EstimacionPreliminar:
    """Genera y persiste una estimación preliminar. No hace commit.

    Usa referencias históricas ajustadas por IPC y valida desvío vs promedio (anti-alucinación).
    """
    cuerpo = texto_para_ia(reclamo, db)
    refs = historicos.buscar_referencias(
        db,
        categoria=reclamo.categoria,
        descripcion=cuerpo,
    )
    confianza_base = historicos.confianza_por_precedentes(refs)

    contexto_refs = []
    meta_inflacion = {}
    for r in refs:
        contexto_refs.append(
            {
                "id": r.id,
                "descripcion": r.descripcion,
                "monto_ajustado_ars": float(r.monto_ajustado),
                "monto_original_ars": float(r.monto_original),
                "similitud": r.similitud,
                "fecha_referencia": r.fecha_referencia,
            }
        )
        if r.meta_inflacion:
            meta_inflacion = r.meta_inflacion

    provider = get_llm_provider()
    try:
        raw = provider.complete_json(
            system=SYSTEM_ESTIMACION,
            user=user_estimacion(
                descripcion=cuerpo,
                categoria=reclamo.categoria,
                prioridad=reclamo.prioridad.value,
                escuela=reclamo.nombre_escuela,
                referencias=contexto_refs,
                confianza_sugerida=confianza_base,
            ),
            schema_hint=_SCHEMA,
        )
        proveedor_nombre = provider.name
    except Exception:
        logger.exception(
            "LLM de estimación no disponible para reclamo %s; se usan solo históricos",
            reclamo.id,
        )
        raw = {}
        proveedor_nombre = "historicos"

    materiales = _as_decimal(raw.get("materiales"))
    mano_obra = _as_decimal(raw.get("mano_obra"))
    otros = _as_decimal(raw.get("otros"))
    total = _as_decimal(raw.get("total"))

    if total <= 0 and refs:
        promedio = sum((r.monto_ajustado for r in refs), Decimal("0")) / len(refs)
        materiales = (promedio * Decimal("0.40")).quantize(Decimal("0.01"))
        mano_obra = (promedio * Decimal("0.50")).quantize(Decimal("0.01"))
        otros = (promedio * Decimal("0.10")).quantize(Decimal("0.01"))
        total = materiales + mano_obra + otros
    elif total <= 0:
        total = materiales + mano_obra + otros

    try:
        confianza_llm = float(raw.get("confianza", confianza_base))
    except (TypeError, ValueError):
        confianza_llm = confianza_base

    requiere_revision, validacion = _validar_desvio(total, refs)
    confianza = _confianza_estimacion(confianza_base, confianza_llm, validacion)

    detalle_llm = raw.get("detalle") if isinstance(raw.get("detalle"), dict) else {}
    justificacion = _justificacion_coherente(
        _justificacion_estimacion(raw, refs, validacion),
        materiales=materiales,
        mano_obra=mano_obra,
        otros=otros,
        total=total,
        confianza=confianza,
        validacion=validacion,
    )
    detalle = {
        **detalle_llm,
        "justificacion": justificacion,
        "referencias_ids": [r.id for r in refs],
        "referencias": contexto_refs,
        "confianza_por_precedentes": confianza_base,
        "factor_inflacion": meta_inflacion.get("factor"),
        "serie_ipc": meta_inflacion.get("serie_ipc"),
        "fuente_inflacion": meta_inflacion.get("fuente_inflacion"),
        "meta_inflacion": meta_inflacion,
        "validacion": validacion,
    }
    if validacion.get("motivo") == "sin_referencias":
        detalle["aviso"] = (
            "No hay datos históricos similares para basar esta estimación. "
            "Se recomienda inspección técnica presencial antes de la aprobación."
        )
    elif validacion.get("motivo") == "desvio_vs_historicos":
        detalle["aviso"] = (
            "El total se aleja de los costos históricos similares; conviene revisarlo."
        )

    estimacion = EstimacionPreliminar(
        reclamo_id=reclamo.id,
        materiales=materiales,
        mano_obra=mano_obra,
        otros=otros,
        total=total,
        confianza=confianza,
        detalle=json.dumps(detalle, ensure_ascii=False),
        proveedor=proveedor_nombre,
        requiere_revision=requiere_revision,
    )
    db.add(estimacion)
    db.flush()

    registro.registrar(
        db,
        tipo=TipoRecomendacionIA.ESTIMACION,
        payload={
            "estimacion_id": estimacion.id,
            "materiales": float(materiales),
            "mano_obra": float(mano_obra),
            "otros": float(otros),
            "total": float(total),
            "validacion": validacion,
        },
        reclamo_id=reclamo.id,
        proveedor=proveedor_nombre,
        confianza=confianza,
        requiere_revision=requiere_revision,
    )

    if transicionar and reclamo.estado == EstadoReclamo.PENDIENTE_REVISION:
        try:
            cambiar_estado(
                db,
                reclamo,
                EstadoReclamo.PENDIENTE_PRESUPUESTO,
                motivo="Estimación preliminar generada por el Motor de IA",
                origen=OrigenCambioEstado.AUTOMATICO,
            )
        except TransicionInvalida:
            logger.warning(
                "No se pudo transicionar reclamo %s tras estimación", reclamo.id
            )

    return estimacion


def sirve_como_ancla_auditoria(estimacion: EstimacionPreliminar | None) -> bool:
    """Sin precedentes, total $0 o confianza 0 no sirven para auditar un presupuesto."""
    from schemas.ai import _detalle_sin_precedentes

    if estimacion is None:
        return False
    if Decimal(estimacion.total or 0) <= 0:
        return False
    if (estimacion.confianza or 0) <= 0:
        return False
    return not _detalle_sin_precedentes(estimacion.detalle)


def ultima_estimacion(db: Session, reclamo_id: int) -> EstimacionPreliminar | None:
    return (
        db.query(EstimacionPreliminar)
        .filter(EstimacionPreliminar.reclamo_id == reclamo_id)
        .order_by(EstimacionPreliminar.fecha.desc())
        .first()
    )


def _promedio_ponderado(refs) -> Decimal:
    """Promedio de montos ajustados ponderado por similitud (evita que un ref flojo sesgue)."""
    pesos = [Decimal(str(max(getattr(r, "similitud", 0) or 0, 0.01))) for r in refs]
    total_peso = sum(pesos, Decimal("0"))
    if total_peso <= 0:
        return Decimal("0")
    return sum((r.monto_ajustado * peso for r, peso in zip(refs, pesos)), Decimal("0")) / total_peso


def _confianza_estimacion(
    confianza_base: float,
    confianza_llm: float,
    validacion: dict,
) -> float:
    """Confianza según precedentes (CU-02) y desvío vs históricos.

    Antes se aplastaba a 0.45 ante cualquier revisión, por eso todas las
    estimaciones mostraban el mismo 45%. Acá varía: sin refs queda baja;
    con refs refleja similitud y cercanía al promedio histórico.
    """
    mezcla = max(0.0, min(1.0, (confianza_base * 0.6) + (confianza_llm * 0.4)))
    motivo = validacion.get("motivo")

    if motivo in ("sin_referencias", "promedio_refs_invalido"):
        return round(min(mezcla, 0.30), 3)

    desvio = validacion.get("desvio")
    if desvio is None:
        return round(mezcla, 3)

    factor = max(0.40, 1.0 - float(desvio))
    return round(max(0.20, min(1.0, mezcla * factor)), 3)


def _validar_desvio(total: Decimal, refs) -> tuple[bool, dict]:
    if not refs:
        return True, {
            "requiere_revision": True,
            "motivo": "sin_referencias",
            "umbral": float(UMBRAL_DESVIO_ESTIMACION),
            "desvio": None,
            "promedio_refs": None,
        }

    promedio = _promedio_ponderado(refs)
    if promedio <= 0:
        return True, {
            "requiere_revision": True,
            "motivo": "promedio_refs_invalido",
            "umbral": float(UMBRAL_DESVIO_ESTIMACION),
            "desvio": None,
            "promedio_refs": float(promedio),
        }

    desvio = abs(total - promedio) / promedio
    requiere = desvio > UMBRAL_DESVIO_ESTIMACION
    return requiere, {
        "requiere_revision": requiere,
        "motivo": "desvio_vs_historicos" if requiere else "ok",
        "umbral": float(UMBRAL_DESVIO_ESTIMACION),
        "desvio": float(desvio.quantize(Decimal("0.0001"))),
        "promedio_refs": float(promedio.quantize(Decimal("0.01"))),
    }


def _nombres_referencias(refs) -> str:
    nombres = [f"«{(r.descripcion or '').strip()}»" for r in refs[:3] if (r.descripcion or "").strip()]
    if not nombres:
        return "trabajos históricos similares"
    if len(nombres) == 1:
        return nombres[0]
    return " y ".join([", ".join(nombres[:-1]), nombres[-1]]) if len(nombres) > 2 else " y ".join(nombres)


def _fmt_ars(valor) -> str:
    entero = int(Decimal(str(valor)).quantize(Decimal("1")))
    return f"${entero:,}".replace(",", ".")


def _formatear_cifras_ars(texto: str) -> str:
    def _reemplazo(match: re.Match) -> str:
        bruto = match.group(0).replace(",", ".")
        try:
            n = Decimal(bruto)
        except Exception:
            return match.group(0)
        if n < 1000:
            return match.group(0)
        return _fmt_ars(n)

    return re.sub(r"\b\d{5,}(?:[.,]\d{1,2})?\b", _reemplazo, texto)


def _quitar_afirmaciones_contradictorias(texto: str, validacion: dict) -> str:
    if validacion.get("motivo") != "desvio_vs_historicos":
        return texto
    mala = re.compile(
        r"sólid|solida|dentro del rango|ajustad[oa]s? dentro|se considera (?:sólid|solida)|alta confianza",
        re.IGNORECASE,
    )
    oraciones = re.split(r"(?<=[.!?])\s+", texto.strip())
    quedaron = [o for o in oraciones if o and not mala.search(o)]
    return " ".join(quedaron).strip()


def _justificacion_coherente(
    texto: str,
    *,
    materiales: Decimal,
    mano_obra: Decimal,
    otros: Decimal,
    total: Decimal,
    confianza: float,
    validacion: dict,
) -> str:
    """La justificación tiene que coincidir con el desglose y con si hay que revisar."""
    cuerpo = _alinear_confianza_en_justificacion(texto, confianza)
    cuerpo = _formatear_cifras_ars(cuerpo)
    cuerpo = _quitar_afirmaciones_contradictorias(cuerpo, validacion)
    desglose = (
        f"El desglose de esta estimación es materiales {_fmt_ars(materiales)}, "
        f"mano de obra {_fmt_ars(mano_obra)} y otros {_fmt_ars(otros)} "
        f"(total {_fmt_ars(total)})."
    )
    if validacion.get("motivo") == "desvio_vs_historicos":
        cierre = " El total se aleja del promedio de los trabajos históricos similares; conviene revisarlo."
    else:
        cierre = ""
    if cuerpo:
        if desglose[:-1] in cuerpo:
            return f"{cuerpo}{cierre}".strip()
        return f"{cuerpo} {desglose}{cierre}".strip()
    return f"{desglose}{cierre}".strip()


def _alinear_confianza_en_justificacion(texto: str, confianza: float) -> str:
    """El badge y el párrafo tienen que decir el mismo porcentaje (el del sistema)."""
    if not texto:
        return texto
    pct = f"{int(round(max(0.0, min(1.0, confianza)) * 100))}%"
    alineado = re.sub(
        r"(?i)(confianza[^\d\n]{0,48})(0[.,]\d{1,3}|\d{1,3}\s*%)",
        lambda m: f"{m.group(1)}{pct}",
        texto,
    )
    alineado = re.sub(
        r"(?i)(\ben\s+)(0[.,]\d{1,3})(?=\s+debido)",
        lambda m: f"{m.group(1)}{pct}",
        alineado,
    )
    return alineado


def _sin_ids_internos(texto: str, refs) -> str:
    """El gestor no ve ids de tabla; si el LLM los cita, se reemplazan por la descripción."""
    por_id = {str(r.id): (r.descripcion or "").strip() for r in refs if getattr(r, "id", None) is not None}

    def _reemplazo(match: re.Match) -> str:
        desc = por_id.get(match.group(1))
        return f"«{desc}»" if desc else "un trabajo histórico similar"

    limpio = re.sub(
        r"(?:el\s+)?(?:precedente|referencia)(?:\s+hist[oó]rico)?\s+(?:id\s*[=:]?\s*)?#?(\d+)",
        _reemplazo,
        texto,
        flags=re.IGNORECASE,
    )
    limpio = re.sub(r"\bid\s*[=:]\s*(\d+)\b", _reemplazo, limpio, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", limpio).strip()


def _justificacion_estimacion(raw: dict, refs, validacion: dict) -> str:
    texto = raw.get("justificacion")
    if not (isinstance(texto, str) and texto.strip()):
        det = raw.get("detalle")
        if isinstance(det, dict):
            nota = det.get("justificacion") or det.get("nota")
            if isinstance(nota, str) and nota.strip():
                texto = nota
    if isinstance(texto, str) and texto.strip():
        return _sin_ids_internos(texto.strip(), refs)
    motivo = validacion.get("motivo")
    if motivo in ("sin_referencias", "promedio_refs_invalido"):
        return (
            "No hay trabajos históricos similares para anclar los montos. "
            "La cifra es orientativa; conviene una inspección técnica antes de aprobar."
        )
    if refs:
        ancla = (
            f"Se ancló a trabajos históricos similares ajustados por inflación: "
            f"{_nombres_referencias(refs)}."
        )
        if motivo == "desvio_vs_historicos":
            return f"{ancla} El total se aleja del promedio de esos trabajos; conviene revisarlo."
        return f"{ancla} El total quedó alineado con esos precedentes."
    return "Estimación preliminar sin ancla histórica suficiente."


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")
