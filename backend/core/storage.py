"""Abstracción de almacenamiento de archivos.

`LocalStorage` guarda los archivos en disco (bind mount de Docker Compose), pensado
para desarrollo. El día que se migre a producción, se puede agregar una implementación
`S3Storage` (boto3, contra S3 real o MinIO) que cumpla la misma interfaz sin tener que
tocar los endpoints que la usan.
"""

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile

UPLOADS_DIR = Path("uploads")

MB = 1024 * 1024


class ArchivoInvalido(Exception):
    """El archivo subido no se acepta. `status_code` es el que corresponde devolver."""

    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code


def _es_jpeg(c: bytes) -> bool:
    return c.startswith(b"\xff\xd8\xff")


def _es_png(c: bytes) -> bool:
    return c.startswith(b"\x89PNG\r\n\x1a\n")


def _es_webp(c: bytes) -> bool:
    return c[:4] == b"RIFF" and c[8:12] == b"WEBP"


def _es_iso_bmff(c: bytes) -> bool:
    # MP4, MOV y 3GP: la segunda "caja" del contenedor arranca en el byte 4.
    return c[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip")


def _es_webm(c: bytes) -> bool:
    return c.startswith(b"\x1a\x45\xdf\xa3")


def _es_pdf(c: bytes) -> bool:
    return c.startswith(b"%PDF-")


# Lo único que se acepta subir: tipo -> (extensión con la que se guarda, tope, cómo
# reconocerlo por su contenido). La extensión la decide el servidor, nunca el nombre que
# manda el cliente, y el contenido tiene que coincidir con el tipo declarado: si no, un
# .html con Content-Type image/png se serviría como página desde el mismo origen que la API.
# Los topes de videos coinciden con `client_max_body_size` de nginx en producción (25m).
TIPOS_ACEPTADOS: dict[str, tuple[str, int, object]] = {
    "image/jpeg": (".jpg", 10 * MB, _es_jpeg),
    "image/png": (".png", 10 * MB, _es_png),
    "image/webp": (".webp", 10 * MB, _es_webp),
    "video/mp4": (".mp4", 25 * MB, _es_iso_bmff),
    "video/quicktime": (".mov", 25 * MB, _es_iso_bmff),
    "video/3gpp": (".3gp", 25 * MB, _es_iso_bmff),
    "video/webm": (".webm", 25 * MB, _es_webm),
    "application/pdf": (".pdf", 10 * MB, _es_pdf),
}

# Las que puede tener un archivo guardado: las de los tipos aceptados y las de los audios
# y videos que llegan por WhatsApp (el tipo lo informa Meta, no un usuario).
EXTENSIONES_SEGURAS = frozenset(
    {ext for ext, _tope, _coincide in TIPOS_ACEPTADOS.values()}
    | {".ogg", ".mp3", ".m4a", ".amr", ".aac", ".bin"}
)

TIPOS_IMAGEN = frozenset({"image/jpeg", "image/png", "image/webp"})
TIPOS_VIDEO = frozenset({"video/mp4", "video/quicktime", "video/3gpp", "video/webm"})
TIPOS_MEDIA = TIPOS_IMAGEN | TIPOS_VIDEO


def _normalizar_mime(mime: str | None) -> str:
    mime = (mime or "").split(";")[0].strip().lower()
    return "image/jpeg" if mime == "image/jpg" else mime


def leer_archivo_validado(archivo: UploadFile, tipos: frozenset[str]) -> tuple[bytes, str]:
    """Lee el archivo subido y devuelve (contenido, tipo) si se acepta.

    Lanza ArchivoInvalido si el tipo no está entre `tipos`, si supera el tope (lo corta
    mientras lee, sin cargarlo entero) o si el contenido no es lo que dice ser.
    """
    mime = _normalizar_mime(archivo.content_type)
    if mime not in tipos or mime not in TIPOS_ACEPTADOS:
        raise ArchivoInvalido("Ese tipo de archivo no está permitido.")
    _extension, tope, coincide = TIPOS_ACEPTADOS[mime]

    contenido = archivo.file.read(tope + 1)
    if len(contenido) > tope:
        raise ArchivoInvalido(
            f"El archivo supera el máximo de {tope // MB} MB para ese tipo.", status_code=413
        )
    if not contenido:
        raise ArchivoInvalido("El archivo está vacío.")
    if not coincide(contenido):
        raise ArchivoInvalido("El contenido del archivo no coincide con su tipo.")
    return contenido, mime


def extension_de(mime: str) -> str:
    """Extensión con la que se guarda un tipo aceptado (o .bin, que se sirve como descarga)."""
    entrada = TIPOS_ACEPTADOS.get(_normalizar_mime(mime))
    return entrada[0] if entrada else ".bin"


class Storage(ABC):
    def guardar(
        self, archivo: UploadFile, subcarpeta: str, tipos: frozenset[str] = TIPOS_MEDIA
    ) -> str:
        """Valida el archivo subido (tipo, tamaño y contenido), lo guarda y devuelve la URL
        pública. Lanza ArchivoInvalido si no se acepta."""
        contenido, mime = leer_archivo_validado(archivo, tipos)
        return self.guardar_bytes(contenido, subcarpeta, extension_de(mime))

    @abstractmethod
    def guardar_bytes(self, contenido: bytes, subcarpeta: str, extension: str) -> str:
        """Guarda bytes crudos y devuelve la URL pública."""

    @abstractmethod
    def eliminar(self, url: str) -> None:
        """Elimina el archivo asociado a una URL devuelta por `guardar`."""


class LocalStorage(Storage):
    def __init__(self, directorio_base: Path = UPLOADS_DIR, url_base: str = "/uploads"):
        self.directorio_base = directorio_base
        self.url_base = url_base

    def guardar_bytes(self, contenido: bytes, subcarpeta: str, extension: str) -> str:
        destino = self.directorio_base / subcarpeta
        destino.mkdir(parents=True, exist_ok=True)
        ext = extension if extension.startswith(".") else f".{extension}"
        # Solo extensiones conocidas: cualquier otra se guarda como .bin (se descarga, no se
        # abre en el navegador).
        if ext not in EXTENSIONES_SEGURAS:
            ext = ".bin"
        nombre_unico = f"{uuid.uuid4().hex}{ext}"
        ruta_archivo = destino / nombre_unico
        ruta_archivo.write_bytes(contenido)
        return f"{self.url_base}/{subcarpeta}/{nombre_unico}"

    def eliminar(self, url: str) -> None:
        if not url.startswith(f"{self.url_base}/"):
            return
        ruta_relativa = url.removeprefix(f"{self.url_base}/")
        (self.directorio_base / ruta_relativa).unlink(missing_ok=True)


storage: Storage = LocalStorage()
