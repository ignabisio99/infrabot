import pytest

from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario


def test_varios_inspectores_comentan_y_se_listan_en_orden(
    client, loguear, crear_reclamo, loguear_contratista_convocado
):
    reclamo = crear_reclamo()

    loguear(TipoUsuario.INSPECTOR, nombre="Ana")
    primero = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "  Techo con filtraciones  "})
    assert primero.status_code == 201
    assert primero.json()["texto"] == "Techo con filtraciones"
    assert primero.json()["autor"] == "Ana"

    loguear(TipoUsuario.INSPECTOR, nombre="Beto")
    client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Revisar instalación eléctrica"})

    # Los ve también el contratista convocado a presupuestar.
    loguear_contratista_convocado(reclamo)
    listado = client.get(f"/reclamos/{reclamo.id}/comentarios").json()
    assert [(c["autor"], c["texto"]) for c in listado] == [
        ("Ana", "Techo con filtraciones"),
        ("Beto", "Revisar instalación eléctrica"),
    ]


@pytest.mark.parametrize("tipo", [TipoUsuario.ADMINISTRADOR, TipoUsuario.CONTRATISTA])
def test_solo_el_inspector_puede_comentar(client, loguear, crear_reclamo, tipo):
    reclamo = crear_reclamo()
    loguear(tipo)

    respuesta = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Hola"})

    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "estado", [EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO]
)
def test_no_se_comenta_un_reclamo_cerrado_pero_se_siguen_viendo(
    client, loguear, crear_reclamo, estado
):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)
    client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Antes del cierre"})
    reclamo.estado = estado

    respuesta = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Después"})

    assert respuesta.status_code == 409
    assert [c["texto"] for c in client.get(f"/reclamos/{reclamo.id}/comentarios").json()] == [
        "Antes del cierre"
    ]


def test_se_comenta_en_ejecucion(client, loguear, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    loguear(TipoUsuario.INSPECTOR)

    respuesta = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "Avance ok"})

    assert respuesta.status_code == 201


def test_comentario_vacio_se_rechaza(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)

    respuesta = client.post(f"/reclamos/{reclamo.id}/comentarios", json={"texto": "   "})

    assert respuesta.status_code == 422


def test_comentar_reclamo_inexistente_da_404(client, loguear):
    loguear(TipoUsuario.INSPECTOR)

    assert client.post("/reclamos/999999/comentarios", json={"texto": "Hola"}).status_code == 404
    assert client.get("/reclamos/999999/comentarios").status_code == 404
