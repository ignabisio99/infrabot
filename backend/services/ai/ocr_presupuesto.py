"""OCR / extracción de ítems desde adjuntos de presupuesto (imagen o PDF)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from core.storage import (
    TIPOS_IMAGEN,
    ArchivoInvalido,
    extension_de,
    leer_archivo_validado,
    storage,
)
from models.adjunto_presupuesto import AdjuntoPresupuesto, TipoAdjuntoPresupuesto
from services.ai.prompts import SYSTEM_OCR_PRESUPUESTO

logger = logging.getLogger(__name__)

_SCHEMA = {
    "task": "ocr_presupuesto",
    "items": [{"descripcion": "", "cantidad": 1, "costo_unitario": 0}],
}

MIN_PDF_TEXT_CHARS = 40


class ExtraccionPresupuestoError(Exception):
    """No se pudo extraer texto útil del PDF / archivo."""


@dataclass(frozen=True)
class ItemExtraido:
    descripcion: str
    cantidad: Decimal
    costo_unitario: Decimal


@dataclass(frozen=True)
class ResultadoExtraccion:
    adjunto_id: int
    url: str
    tipo: TipoAdjuntoPresupuesto
    items: list[ItemExtraido]
    proveedor: str
    metodo: str


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _extraer_texto_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    partes = []
    for page in reader.pages[:10]:
        partes.append(page.extract_text() or "")
    return "\n".join(partes).strip()


def extraer_items_desde_archivo(
    db: Session,
    archivo: UploadFile,
) -> ResultadoExtraccion:
    """Guarda el adjunto y extrae ítems. No crea Presupuesto."""
    # Tipo, tamaño y contenido los valida el storage; la extensión sale del tipo.
    try:
        data, mime = leer_archivo_validado(archivo, TIPOS_IMAGEN | {"application/pdf"})
    except ArchivoInvalido as e:
        raise ExtraccionPresupuestoError(
            "Formato no soportado. Usá imagen (JPEG/PNG/WebP) o PDF."
            if "permitido" in e.mensaje
            else e.mensaje
        ) from e

    if mime == "application/pdf":
        tipo = TipoAdjuntoPresupuesto.PDF
        texto = _extraer_texto_pdf(data)
        if len(texto) < MIN_PDF_TEXT_CHARS:
            raise ExtraccionPresupuestoError(
                "El PDF no tiene texto extraíble suficiente. "
                "Subí una foto/imagen del presupuesto o un PDF con texto seleccionable."
            )
        url = storage.guardar_bytes(data, "presupuestos", extension_de(mime))
        provider = get_llm_provider()
        raw = provider.complete_json(
            system=SYSTEM_OCR_PRESUPUESTO,
            user=f"Texto extraído del PDF:\n{texto[:8000]}",
            schema_hint=_SCHEMA,
        )
        metodo = "pdf_texto+llm"
    else:
        tipo = TipoAdjuntoPresupuesto.IMAGEN
        url = storage.guardar_bytes(data, "presupuestos", extension_de(mime))
        raw_bytes = data
        provider = get_llm_provider()
        raw = provider.complete_json_with_images(
            system=SYSTEM_OCR_PRESUPUESTO,
            user="Extraé los ítems del presupuesto en la imagen.",
            images=[raw_bytes],
            mime_types=[mime],
            schema_hint=_SCHEMA,
        )
        metodo = "vision"

    items_raw = raw.get("items") or []
    items: list[ItemExtraido] = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        desc = str(it.get("descripcion") or "").strip()
        if not desc:
            continue
        items.append(
            ItemExtraido(
                descripcion=desc,
                cantidad=_as_decimal(it.get("cantidad") or 1),
                costo_unitario=_as_decimal(it.get("costo_unitario")),
            )
        )

    adjunto = AdjuntoPresupuesto(
        presupuesto_id=None,
        nombre_archivo=(archivo.filename or Path(url).name)[:255],
        url=url,
        tipo=tipo,
    )
    db.add(adjunto)
    db.flush()

    return ResultadoExtraccion(
        adjunto_id=adjunto.id,
        url=url,
        tipo=tipo,
        items=items,
        proveedor=provider.name,
        metodo=metodo,
    )
