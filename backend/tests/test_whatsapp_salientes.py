"""El simulador tiene que ver el mensaje aunque el número tenga guiones o el prefijo sim."""

from core.whatsapp_client import (
    limpiar_historial_salientes,
    obtener_historial_salientes,
    registrar_saliente,
)


def test_el_chat_con_guiones_encuentra_el_numero_normalizado():
    limpiar_historial_salientes()
    registrar_saliente("botones", "541146665678", "¿Terminaste el trabajo?")

    hallados = obtener_historial_salientes(to="sim011-4666-5678")

    assert len(hallados) == 1
    assert "Terminaste" in hallados[0]["body"]
    limpiar_historial_salientes()
