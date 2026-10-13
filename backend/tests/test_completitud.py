from services.ai.completitud import evaluar_completitud_heuristica


def test_heuristica_pide_escuela_y_ubicacion_si_faltan():
    r = evaluar_completitud_heuristica(
        escuela="",
        ubicacion="acá",
        descripcion="no anda el agua",
    )
    campos = {f.campo for f in r.faltantes}
    assert r.completo is False
    assert "nombre_escuela" in campos
    assert "ubicacion" in campos
    assert r.proveedor == "heuristica"
    assert len(r.faltantes) <= 2


def test_heuristica_completa_si_hay_detalle():
    r = evaluar_completitud_heuristica(
        escuela="Escuela N° 3",
        ubicacion="baño del primer piso, sector de nenas",
        descripcion=(
            "Desde ayer no funciona el agua en los baños del primer piso "
            "y afecta a toda la escuela."
        ),
    )
    assert r.completo is True
    assert r.faltantes == []
