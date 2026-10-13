from types import SimpleNamespace

from services.ai.contexto_reclamo import observaciones_utiles, texto_para_ia


def test_observaciones_utiles_saca_marcas_de_sistema():
    obs = (
        "[Info adicional 12/10/2026 20:00] Está en el aula 4 del 1er piso\n"
        "Pendiente de intervención: el contratista no respondió\n"
        "[DERIVADO A OPERADOR] confianza baja"
    )
    utiles = observaciones_utiles(obs)
    assert "aula 4" in utiles
    assert "Pendiente de intervención" not in utiles
    assert "DERIVADO" not in utiles
    assert "[Info adicional" not in utiles


def test_texto_para_ia_no_usa_avances_ni_sistema():
    reclamo = SimpleNamespace(
        id=8,
        descripcion="Se rompieron 5 computadoras",
        observaciones=(
            "[Info adicional 12/10] Son del aula de informática\n"
            "Pendiente de intervención: sin respuesta\n"
            "[WhatsApp — Electricidad del Sur] Avance 70%\n"
            "[IA visión] Se ve un tablero abierto"
        ),
    )
    texto = texto_para_ia(reclamo)
    assert "aula de informática" in texto
    assert "Avance 70%" not in texto
    assert "Pendiente de intervención" not in texto
    assert "tablero abierto" not in texto


def test_texto_para_ia_junta_descripcion_e_info_adicional():
    reclamo = SimpleNamespace(
        id=1,
        descripcion="Se quemó el tablero",
        observaciones="[Info adicional 12/10] Hay olor a quemado en el aula 3",
    )
    texto = texto_para_ia(reclamo)
    assert "Se quemó el tablero" in texto
    assert "aula 3" in texto
    assert "Información adicional" in texto
