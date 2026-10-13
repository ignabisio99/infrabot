from core.whatsapp_handler import (
    _descripcion_debil,
    _es_comando,
    _es_comando_listo,
    _fusionar_descripcion,
    _incorporar_detalle,
    _normalizar_comando,
    _parece_descripcion_reclamo,
    _parece_solo_presentacion,
    _sin_saludo_inicial,
)


def test_listo_con_signos_es_comando():
    assert _normalizar_comando("¡Listo!") == "listo"
    assert _es_comando("¡Listo!", "listo", "ok")
    assert _es_comando("Listo.", "listo")
    assert not _es_comando("listo para las fotos", "listo")
    assert _es_comando_listo("¡Listo!")
    assert _es_comando_listo("¡Lito, lito, chatelito!")
    assert not _es_comando_listo("listo para las fotos")


def test_saludo_solo_no_es_reclamo():
    assert _sin_saludo_inicial("hola") == ""
    assert _sin_saludo_inicial("hola buenas") == ""
    assert not _parece_descripcion_reclamo("hola")
    assert not _parece_descripcion_reclamo("buenas tardes")
    assert _parece_solo_presentacion("Hola, este es el número 5.")
    assert not _parece_descripcion_reclamo("Hola, este es el número 5.")


def test_relato_sin_palabras_clave_es_reclamo():
    texto = "se está cayendo el cielo raso del comedor"
    assert not _parece_solo_presentacion(texto)
    assert _parece_descripcion_reclamo(texto)
    datos = {}
    _incorporar_detalle(datos, "Hola, este es el número 5.")
    assert not datos.get("descripcion")
    _incorporar_detalle(datos, texto)
    assert "cielo raso" in (datos.get("descripcion") or "").lower()
    assert not _descripcion_debil(datos["descripcion"])
    unido = _fusionar_descripcion("este es el número 5", texto)
    assert "cielo raso" in unido.lower()


def test_saludo_mas_problema_es_reclamo():
    texto = (
        "hola buenas tengo un problema mi escuela está funcionando mal "
        "el tablero de control"
    )
    assert "tablero" in _sin_saludo_inicial(texto).lower()
    assert _parece_descripcion_reclamo(texto)
    assert _parece_descripcion_reclamo(
        "hay una pérdida de agua en el baño de la escuela técnica"
    )
