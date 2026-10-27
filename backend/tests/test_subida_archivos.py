"""Subida de archivos: tipo, tamaño y contenido validados; extensión puesta por el servidor;
y los archivos servidos sin que el navegador los pueda abrir como página."""

import io
import uuid

import pytest

import api.reclamos
from core.storage import (
    MB,
    UPLOADS_DIR,
    ArchivoInvalido,
    LocalStorage,
    leer_archivo_validado,
)
from models.usuario import TipoUsuario

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
HTML = b"<html><script>fetch('/auth/me')</script></html>"
PDF = b"%PDF-1.4\n" + b"x" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32


@pytest.fixture
def subir(client, loguear, crear_reclamo, monkeypatch, tmp_path):
    """Sube un archivo a un reclamo como inspector; los archivos van a un directorio temporal."""
    monkeypatch.setattr(api.reclamos, "storage", LocalStorage(directorio_base=tmp_path))
    monkeypatch.setattr(api.reclamos, "post_fotos_reclamo", lambda db, reclamo: None)
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)

    def _subir(nombre, contenido, tipo):
        return client.post(
            f"/reclamos/{reclamo.id}/fotos", files={"archivo": (nombre, contenido, tipo)}
        )

    _subir.directorio = tmp_path
    return _subir


def test_un_html_que_dice_ser_png_se_rechaza(subir):
    respuesta = subir("foto.png", HTML, "image/png")

    assert respuesta.status_code == 400
    assert "no coincide" in respuesta.json()["detail"]
    assert not any(subir.directorio.rglob("*.*"))


def test_la_extension_la_pone_el_servidor_no_el_nombre(subir):
    respuesta = subir("ataque.html", PNG, "image/png")

    assert respuesta.status_code == 201
    url = respuesta.json()["url"]
    assert url.endswith(".png") and ".html" not in url
    assert respuesta.json()["nombre_archivo"] == "ataque.html"  # solo se muestra


def test_un_tipo_no_permitido_se_rechaza(subir):
    respuesta = subir("pagina.html", HTML, "text/html")

    assert respuesta.status_code == 400
    assert "imagen" in respuesta.json()["detail"]


def test_una_foto_de_mas_de_10_mb_se_rechaza(subir):
    grande = PNG + b"\x00" * (10 * MB)

    respuesta = subir("grande.png", grande, "image/png")

    assert respuesta.status_code == 413
    assert "10 MB" in respuesta.json()["detail"]


def test_un_video_valido_entra(subir):
    respuesta = subir("obra.mp4", MP4, "video/mp4")

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo"] == "VIDEO"
    assert respuesta.json()["url"].endswith(".mp4")


def _archivo(contenido, tipo):
    from starlette.datastructures import Headers, UploadFile

    return UploadFile(
        file=io.BytesIO(contenido), filename="x", headers=Headers({"content-type": tipo})
    )


def test_un_pdf_falso_se_rechaza():
    with pytest.raises(ArchivoInvalido):
        leer_archivo_validado(_archivo(HTML, "application/pdf"), frozenset({"application/pdf"}))
    contenido, mime = leer_archivo_validado(
        _archivo(PDF, "application/pdf"), frozenset({"application/pdf"})
    )
    assert mime == "application/pdf" and contenido == PDF


def test_guardar_bytes_con_una_extension_desconocida_queda_como_bin(tmp_path):
    url = LocalStorage(directorio_base=tmp_path).guardar_bytes(HTML, "x", ".html")

    assert url.endswith(".bin")


def test_los_archivos_se_sirven_sin_poder_correr_como_pagina(client):
    carpeta = UPLOADS_DIR / f"test-{uuid.uuid4().hex}"
    carpeta.mkdir(parents=True)
    try:
        (carpeta / "foto.png").write_bytes(PNG)
        (carpeta / "adjunto.pdf").write_bytes(PDF)

        foto = client.get(f"/uploads/{carpeta.name}/foto.png")
        pdf = client.get(f"/uploads/{carpeta.name}/adjunto.pdf")
    finally:
        for archivo in carpeta.iterdir():
            archivo.unlink()
        carpeta.rmdir()

    assert foto.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in foto.headers["content-security-policy"]
    # El PDF no lleva sandbox (Chrome bloquearía su visor), pero sí nosniff.
    assert pdf.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in pdf.headers


def test_extraer_presupuesto_de_un_archivo_disfrazado_falla():
    from services.ai.ocr_presupuesto import ExtraccionPresupuestoError, extraer_items_desde_archivo

    with pytest.raises(ExtraccionPresupuestoError):
        extraer_items_desde_archivo(None, _archivo(HTML, "application/pdf"))
