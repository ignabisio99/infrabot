from datetime import date
from decimal import Decimal
from pathlib import Path

from models.referencia_costo import ReferenciaCosto
from services.referencias_costo import cargar_referencias_si_faltan, sincronizar_desde_csv


def test_carga_csv_solo_si_faltan(db, tmp_path):
    csv_path = Path(tmp_path) / "refs.csv"
    csv_path.write_text(
        "categoria,descripcion,monto_ars,fecha_referencia,unidad,fuente\n"
        "Electricidad,Tablero escolar,180000,2024-06-01,trabajo,seed_csv\n"
        "Plomería,Pérdida en baño,75000,2024-08-01,baño,seed_csv\n",
        encoding="utf-8",
    )

    primera = cargar_referencias_si_faltan(db, str(csv_path))
    db.flush()
    assert primera == 2
    assert db.query(ReferenciaCosto).count() == 2

    segunda = cargar_referencias_si_faltan(db, str(csv_path))
    db.flush()
    assert segunda == 0
    assert db.query(ReferenciaCosto).count() == 2


def test_carga_csv_no_pisa_existente(db, tmp_path):
    db.add(
        ReferenciaCosto(
            categoria="Electricidad",
            descripcion="Tablero escolar",
            monto_ars=Decimal("999"),
            fecha_referencia=date(2020, 1, 1),
            fuente="manual",
        )
    )
    db.flush()

    csv_path = Path(tmp_path) / "refs.csv"
    csv_path.write_text(
        "categoria,descripcion,monto_ars,fecha_referencia,unidad,fuente\n"
        "Electricidad,Tablero escolar,180000,2024-06-01,trabajo,seed_csv\n",
        encoding="utf-8",
    )

    assert cargar_referencias_si_faltan(db, str(csv_path)) == 0
    db.flush()
    existente = db.query(ReferenciaCosto).one()
    assert existente.monto_ars == Decimal("999.00")
    assert existente.fuente == "manual"


def test_sincronizar_csv_actualiza_si_cambio(db, tmp_path):
    csv_path = Path(tmp_path) / "refs.csv"
    csv_path.write_text(
        "categoria,descripcion,monto_ars,fecha_referencia,unidad,fuente\n"
        "Electricidad,Tablero escolar,180000,2024-06-01,trabajo,seed_csv\n",
        encoding="utf-8",
    )
    sincronizar_desde_csv(db, str(csv_path))
    db.flush()

    csv_path.write_text(
        "categoria,descripcion,monto_ars,fecha_referencia,unidad,fuente\n"
        "Electricidad,Tablero escolar,200000,2025-01-01,trabajo,seed_csv\n"
        "Plomería,Pérdida en baño,75000,2024-08-01,baño,seed_csv\n",
        encoding="utf-8",
    )
    resultado = sincronizar_desde_csv(db, str(csv_path))
    db.flush()
    assert resultado.creadas == 1
    assert resultado.actualizadas == 1
    tablero = (
        db.query(ReferenciaCosto)
        .filter(ReferenciaCosto.descripcion == "Tablero escolar")
        .one()
    )
    assert tablero.monto_ars == Decimal("200000.00")
    assert tablero.fecha_referencia == date(2025, 1, 1)


def test_sincronizar_csv_no_pisa_presupuesto(db, tmp_path):
    db.add(
        ReferenciaCosto(
            categoria="Electricidad",
            descripcion="Tablero escolar",
            monto_ars=Decimal("999"),
            fecha_referencia=date(2020, 1, 1),
            fuente="presupuesto:12",
        )
    )
    db.flush()
    csv_path = Path(tmp_path) / "refs.csv"
    csv_path.write_text(
        "categoria,descripcion,monto_ars,fecha_referencia,unidad,fuente\n"
        "Electricidad,Tablero escolar,180000,2024-06-01,trabajo,seed_csv\n",
        encoding="utf-8",
    )
    resultado = sincronizar_desde_csv(db, str(csv_path))
    db.flush()
    assert resultado.actualizadas == 0
    assert db.query(ReferenciaCosto).one().monto_ars == Decimal("999.00")
