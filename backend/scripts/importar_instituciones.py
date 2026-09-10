"""Importa/actualiza el padrón de instituciones desde un CSV.

Normalmente NO hace falta correr esto: el backend carga el padrón automáticamente al
arrancar si la tabla está vacía (ver services/instituciones.cargar_padron_si_vacio).

Usar este script solo para forzar una recarga o cargar un CSV distinto:
    python scripts/importar_instituciones.py [ruta_csv]

Sin argumento usa el CSV interno (backend/data/instituciones.csv).
El CSV debe tener las columnas: Localidad, Identificador, Nombre, Domicilio, C. P.
Es idempotente: matchea por identificador, actualiza en vez de duplicar.
"""

import os
import sys

# Permite ejecutar el script agregando el directorio raíz del backend (/app) al path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Base, SessionLocal, engine
from services.instituciones import importar_padron


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ruta = sys.argv[1] if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        creados, actualizados = importar_padron(db, ruta)
        print(f"Instituciones importadas: {creados} nuevas, {actualizados} actualizadas.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
