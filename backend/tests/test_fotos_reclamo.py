import pytest

import api.reclamos
from core.storage import LocalStorage
from models.foto_reclamo import FotoReclamo
from models.reclamo import EstadoReclamo
from models.usuario import TipoUsuario

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture(autouse=True)
def sin_efectos_externos(monkeypatch, tmp_path):
    """Guarda los archivos en un directorio temporal y no dispara el análisis de IA."""
    monkeypatch.setattr(api.reclamos, "storage", LocalStorage(directorio_base=tmp_path))
    monkeypatch.setattr(api.reclamos, "post_fotos_reclamo", lambda db, reclamo: None)


def _subir(client, reclamo_id, nombre="grieta.png", tipo="image/png"):
    return client.post(
        f"/reclamos/{reclamo_id}/fotos", files={"archivo": (nombre, PNG, tipo)}
    )


def test_el_inspector_sube_una_foto_y_queda_con_su_autoria(
    client, loguear, crear_reclamo, loguear_contratista_convocado
):
    reclamo = crear_reclamo()
    inspector = loguear(TipoUsuario.INSPECTOR, nombre="Ana")

    respuesta = _subir(client, reclamo.id)

    assert respuesta.status_code == 201
    foto = respuesta.json()
    assert foto["tipo"] == "IMAGEN"
    assert foto["nombre_archivo"] == "grieta.png"
    assert foto["usuario_id"] == inspector.id
    assert foto["autor"] == "Ana"
    assert foto["autor_tipo"] == "INSPECTOR"

    loguear_contratista_convocado(reclamo)
    fotos = client.get(f"/reclamos/{reclamo.id}").json()["fotos"]
    assert [(f["id"], f["autor"]) for f in fotos] == [(foto["id"], "Ana")]


def test_el_admin_sigue_pudiendo_subir_fotos(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.ADMINISTRADOR, nombre="Admin")

    respuesta = _subir(client, reclamo.id)

    assert respuesta.status_code == 201
    assert respuesta.json()["autor"] == "Admin"


def test_el_contratista_no_puede_subir_fotos(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.CONTRATISTA)

    assert _subir(client, reclamo.id).status_code == 403


@pytest.mark.parametrize(
    "estado", [EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO]
)
def test_el_inspector_no_sube_fotos_a_un_reclamo_cerrado(
    client, loguear, crear_reclamo, estado
):
    reclamo = crear_reclamo(estado=estado)
    loguear(TipoUsuario.INSPECTOR)

    assert _subir(client, reclamo.id).status_code == 409


def test_el_admin_sube_fotos_aunque_el_reclamo_este_cerrado(client, loguear, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.FINALIZADO)
    loguear(TipoUsuario.ADMINISTRADOR)

    assert _subir(client, reclamo.id).status_code == 201


def test_el_inspector_sube_fotos_en_ejecucion(client, loguear, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    loguear(TipoUsuario.INSPECTOR)

    assert _subir(client, reclamo.id).status_code == 201


def test_se_rechaza_un_archivo_que_no_es_imagen_ni_video(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)

    respuesta = _subir(client, reclamo.id, nombre="informe.pdf", tipo="application/pdf")

    assert respuesta.status_code == 400


def test_subir_foto_a_reclamo_inexistente_da_404(client, loguear):
    loguear(TipoUsuario.INSPECTOR)

    assert _subir(client, 999999).status_code == 404


def _comentarios(client, reclamo_id):
    return client.get(f"/reclamos/{reclamo_id}/comentarios").json()


def test_el_inspector_quita_su_foto_y_queda_constancia(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR, nombre="Ana")
    foto_id = _subir(client, reclamo.id, nombre="grieta.png").json()["id"]

    respuesta = client.delete(f"/reclamos/{reclamo.id}/fotos/{foto_id}")

    assert respuesta.status_code == 204
    assert client.get(f"/reclamos/{reclamo.id}").json()["fotos"] == []
    [comentario] = _comentarios(client, reclamo.id)
    assert comentario["usuario_id"] is None
    assert comentario["texto"] == "[Sistema]\nAna (inspector) quitó la foto grieta.png."


@pytest.mark.parametrize("autor", [TipoUsuario.INSPECTOR, TipoUsuario.ADMINISTRADOR])
def test_el_inspector_no_quita_fotos_ajenas(client, loguear, crear_reclamo, autor):
    reclamo = crear_reclamo()
    loguear(autor, nombre="Otro")
    foto_id = _subir(client, reclamo.id).json()["id"]
    loguear(TipoUsuario.INSPECTOR, nombre="Ana")

    respuesta = client.delete(f"/reclamos/{reclamo.id}/fotos/{foto_id}")

    assert respuesta.status_code == 403
    assert len(client.get(f"/reclamos/{reclamo.id}").json()["fotos"]) == 1
    assert _comentarios(client, reclamo.id) == []


def test_el_inspector_no_quita_fotos_que_llegaron_por_whatsapp(client, db, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    foto = FotoReclamo(reclamo_id=reclamo.id, nombre_archivo="wpp.jpg", url="/uploads/x/wpp.jpg")
    db.add(foto)
    db.flush()
    loguear(TipoUsuario.INSPECTOR)

    assert client.delete(f"/reclamos/{reclamo.id}/fotos/{foto.id}").status_code == 403


@pytest.mark.parametrize(
    "estado", [EstadoReclamo.FINALIZADO, EstadoReclamo.RECHAZADO, EstadoReclamo.CANCELADO]
)
def test_el_inspector_no_quita_fotos_de_un_reclamo_cerrado(
    client, loguear, crear_reclamo, estado
):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)
    foto_id = _subir(client, reclamo.id).json()["id"]
    reclamo.estado = estado

    respuesta = client.delete(f"/reclamos/{reclamo.id}/fotos/{foto_id}")

    assert respuesta.status_code == 409
    assert _comentarios(client, reclamo.id) == []


def test_el_admin_quita_cualquier_foto_sin_dejar_comentario(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)
    foto_id = _subir(client, reclamo.id).json()["id"]
    reclamo.estado = EstadoReclamo.FINALIZADO
    loguear(TipoUsuario.ADMINISTRADOR)

    assert client.delete(f"/reclamos/{reclamo.id}/fotos/{foto_id}").status_code == 204
    assert _comentarios(client, reclamo.id) == []


def test_el_contratista_no_quita_fotos(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)
    foto_id = _subir(client, reclamo.id).json()["id"]
    loguear(TipoUsuario.CONTRATISTA)

    assert client.delete(f"/reclamos/{reclamo.id}/fotos/{foto_id}").status_code == 403


def test_quitar_foto_inexistente_da_404(client, loguear, crear_reclamo):
    reclamo = crear_reclamo()
    loguear(TipoUsuario.INSPECTOR)

    assert client.delete(f"/reclamos/{reclamo.id}/fotos/999999").status_code == 404
