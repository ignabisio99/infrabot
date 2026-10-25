from models.reclamo import EstadoReclamo
from services.ai import vision_reclamo
from services.ai.vision_reclamo import AnalisisMediaReclamo


def test_analizar_fotos_no_modifica_el_reclamo(client, crear_reclamo, monkeypatch):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_REVISION, observaciones="Original")
    monkeypatch.setattr(
        vision_reclamo,
        "analizar_media_reclamo",
        lambda _db, r: AnalisisMediaReclamo(
            reclamo_id=r.id,
            hallazgos=["Mancha de humedad en el cielorraso"],
            severidad="MEDIA",
            sugerencia_descripcion="Filtración en el techo del aula.",
            fotos_analizadas=1,
            proveedor="prueba",
        ),
    )

    # El parámetro que agregaba la sugerencia a las observaciones ya no existe: se ignora.
    respuesta = client.post(
        f"/ai/reclamos/{reclamo.id}/analizar-media?enriquecer_descripcion=true"
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["sugerencia_descripcion"] == "Filtración en el techo del aula."
    assert "enriquecido" not in respuesta.json()
    assert reclamo.observaciones == "Original"
