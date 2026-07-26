"""Carga datos de ejemplo en la base para tener un entorno de desarrollo consistente.

Uso:
    docker compose exec backend python seed.py          # solo si las tablas están vacías
    docker compose exec backend python seed.py --reset   # borra todo y vuelve a cargar
"""

import sys

from core.database import Base, SessionLocal, engine
from models.contratista import Contratista
from models.presupuesto import ItemPresupuesto, Presupuesto
from models.reclamo import PrioridadReclamo, Reclamo

CONTRATISTAS = [
    dict(
        nombre_empresa="Electricidad del Sur SRL",
        telefono="011-4555-1234",
        direccion="Av. Rivadavia 4500, CABA",
        especialidad="Electricidad",
        calificacion=4,
    ),
    dict(
        nombre_empresa="Plomería Integral SA",
        telefono="011-4666-5678",
        direccion="Calle Falsa 123, San Justo",
        especialidad="Plomería",
        calificacion=5,
    ),
    dict(
        nombre_empresa="Construcciones Belgrano",
        telefono="011-4777-9012",
        direccion="Av. Cabildo 2100, CABA",
        especialidad="Albañilería",
        calificacion=3,
    ),
]

RECLAMOS = [
    dict(
        nombre_escuela="Escuela N°12 - Manuel Belgrano",
        ubicacion="Tablero principal, ala norte",
        prioridad=PrioridadReclamo.ALTA,
        categoria="Electricidad",
        descripcion="Cortocircuito en el tablero principal del ala norte del edificio.",
        observaciones="Se cortó la luz en 3 aulas.",
    ),
    dict(
        nombre_escuela="Escuela N°5 - Domingo Sarmiento",
        ubicacion="Baño, planta baja",
        prioridad=PrioridadReclamo.MEDIA,
        categoria="Plomería",
        descripcion="Pérdida de agua en el baño de planta baja.",
        observaciones=None,
    ),
    dict(
        nombre_escuela="Escuela N°8 - José de San Martín",
        ubicacion="Patio interno",
        prioridad=PrioridadReclamo.BAJA,
        categoria="Albañilería",
        descripcion="Grieta en la pared del patio interno.",
        observaciones="No representa riesgo inmediato.",
    ),
]


def reset(db):
    db.query(ItemPresupuesto).delete()
    db.query(Presupuesto).delete()
    db.query(Reclamo).delete()
    db.query(Contratista).delete()
    db.commit()


def seed(db):
    contratistas = [Contratista(**data) for data in CONTRATISTAS]
    db.add_all(contratistas)

    reclamos = [Reclamo(**data) for data in RECLAMOS]
    db.add_all(reclamos)
    db.flush()

    db.add(
        Presupuesto(
            reclamo_id=reclamos[0].id,
            contratista_id=contratistas[0].id,
            observaciones="Presupuesto para reparación del tablero.",
            items=[
                ItemPresupuesto(descripcion="Mano de obra", cantidad=8, costo_unitario=5000),
                ItemPresupuesto(descripcion="Tablero eléctrico nuevo", cantidad=1, costo_unitario=45000),
            ],
        )
    )
    db.add(
        Presupuesto(
            reclamo_id=reclamos[1].id,
            contratista_id=contratistas[1].id,
            observaciones=None,
            items=[
                ItemPresupuesto(descripcion="Cañería PVC 3/4", cantidad=10, costo_unitario=1200),
                ItemPresupuesto(descripcion="Mano de obra", cantidad=4, costo_unitario=5000),
            ],
        )
    )
    db.commit()


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if "--reset" in sys.argv:
            reset(db)
        elif db.query(Reclamo).first() is not None:
            print("Ya hay datos cargados. Usá --reset si querés borrar todo y recargar.")
            return
        seed(db)
        print("Datos de ejemplo cargados correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
