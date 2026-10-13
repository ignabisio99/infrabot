"""Análisis visual de fotos de reclamos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from core.storage import UPLOADS_DIR
from models.foto_reclamo import TipoMedia
from models.reclamo import Reclamo
from services.ai.contexto_reclamo import texto_para_ia
from services.ai.prompts import SYSTEM_VISION_RECLAMO

logger = logging.getLogger(__name__)

_SCHEMA = {
    "task": "vision_reclamo",
    "hallazgos": [],
    "severidad": "MEDIA",
    "sugerencia_descripcion": "",
}


@dataclass(frozen=True)
class AnalisisMediaReclamo:
    reclamo_id: int
    hallazgos: list[str]
    severidad: str
    sugerencia_descripcion: str
    fotos_analizadas: int
    proveedor: str


def _ruta_desde_url(url: str) -> Path | None:
    if not url.startswith("/uploads/"):
        return None
    rel = url.removeprefix("/uploads/")
    path = UPLOADS_DIR / rel
    return path if path.is_file() else None


def analizar_media_reclamo(db: Session, reclamo: Reclamo) -> AnalisisMediaReclamo:
    imagenes: list[bytes] = []
    mimes: list[str] = []
    for foto in reclamo.fotos or []:
        if foto.tipo != TipoMedia.IMAGEN:
            continue
        path = _ruta_desde_url(foto.url)
        if path is None:
            continue
        data = path.read_bytes()
        imagenes.append(data)
        suffix = path.suffix.lower()
        mime = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(
            suffix, "image/jpeg"
        )
        mimes.append(mime)

    if not imagenes:
        return AnalisisMediaReclamo(
            reclamo_id=reclamo.id,
            hallazgos=[],
            severidad="MEDIA",
            sugerencia_descripcion="",
            fotos_analizadas=0,
            proveedor="n/a",
        )

    provider = get_llm_provider()
    user = (
        f"Escuela: {reclamo.nombre_escuela}\n"
        f"Ubicación: {reclamo.ubicacion}\n"
        f"Descripción actual: {texto_para_ia(reclamo)}\n"
        f"Analizá {len(imagenes)} foto(s) adjunta(s)."
    )
    raw = provider.complete_json_with_images(
        system=SYSTEM_VISION_RECLAMO,
        user=user,
        images=imagenes[:4],
        mime_types=mimes[:4],
        schema_hint=_SCHEMA,
    )
    hallazgos = raw.get("hallazgos") or []
    if not isinstance(hallazgos, list):
        hallazgos = [str(hallazgos)]
    return AnalisisMediaReclamo(
        reclamo_id=reclamo.id,
        hallazgos=[str(h) for h in hallazgos],
        severidad=str(raw.get("severidad") or "MEDIA").upper(),
        sugerencia_descripcion=str(raw.get("sugerencia_descripcion") or "").strip(),
        fotos_analizadas=len(imagenes[:4]),
        proveedor=provider.name,
    )
