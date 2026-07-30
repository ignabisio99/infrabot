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


class Storage(ABC):
    @abstractmethod
    def guardar(self, archivo: UploadFile, subcarpeta: str) -> str:
        """Guarda el archivo y devuelve la URL pública para acceder a él."""

    @abstractmethod
    def eliminar(self, url: str) -> None:
        """Elimina el archivo asociado a una URL devuelta por `guardar`."""


class LocalStorage(Storage):
    def __init__(self, directorio_base: Path = UPLOADS_DIR, url_base: str = "/uploads"):
        self.directorio_base = directorio_base
        self.url_base = url_base

    def guardar(self, archivo: UploadFile, subcarpeta: str) -> str:
        destino = self.directorio_base / subcarpeta
        destino.mkdir(parents=True, exist_ok=True)

        extension = Path(archivo.filename or "").suffix
        nombre_unico = f"{uuid.uuid4().hex}{extension}"
        ruta_archivo = destino / nombre_unico

        with ruta_archivo.open("wb") as buffer:
            buffer.write(archivo.file.read())

        return f"{self.url_base}/{subcarpeta}/{nombre_unico}"

    def eliminar(self, url: str) -> None:
        if not url.startswith(f"{self.url_base}/"):
            return
        ruta_relativa = url.removeprefix(f"{self.url_base}/")
        (self.directorio_base / ruta_relativa).unlink(missing_ok=True)


storage: Storage = LocalStorage()
