import pytest

import api.presupuestos
import services.coordinacion_visita
from core.dependencies import get_current_user
from main import app
from models.reclamo import EstadoReclamo
from models.usuario import EstadoUsuario, TipoUsuario, Usuario

ITEMS = [{"descripcion": "Membrana", "cantidad": "2", "costo_unitario": "1000"}]


@pytest.fixture(autouse=True)
def sin_efectos_externos(monkeypatch):
    """Sin auditoría de IA ni envíos reales; los avisos quedan anotados para mirarlos."""
    avisos = []
    monkeypatch.setattr(api.presupuestos, "post_presupuesto", lambda db, p: None)
    monkeypatch.setattr(
        api.presupuestos, "enviar_mensaje", lambda telefono, texto: avisos.append(texto)
    )
    monkeypatch.setattr(
        api.presupuestos, "enviar_rechazo_presupuesto", lambda *args: avisos.append(args)
    )
    monkeypatch.setattr(
        services.coordinacion_visita, "iniciar_coordinacion", lambda db, reclamo, contratista: None
    )
    return avisos


@pytest.fixture
def loguear_contratista(db, crear_contratista):
    """Loguea como el contratista `nombre`, creándolo (usuario + ficha) la primera vez."""
    registrados = {}

    def _loguear(nombre="Constructora"):
        if nombre not in registrados:
            usuario = Usuario(
                nombre=nombre,
                email=f"{nombre.lower()}@test.local",
                password_hash="x",
                tipo=TipoUsuario.CONTRATISTA,
                estado=EstadoUsuario.APROBADO,
            )
            db.add(usuario)
            db.flush()
            ficha = crear_contratista(nombre_empresa=nombre)
            ficha.usuario_id = usuario.id
            db.flush()
            registrados[nombre] = (usuario, ficha)

        usuario, ficha = registrados[nombre]
        app.dependency_overrides[get_current_user] = lambda: usuario
        return ficha

    return _loguear


def _cargar(client, reclamo, ficha, items=ITEMS):
    return client.post(
        "/presupuestos",
        json={"reclamo_id": reclamo.id, "contratista_id": ficha.id, "items": items},
    )


def _rechazar(client, presupuesto_id, motivo="Precio fuera de mercado"):
    return client.post(
        f"/presupuestos/{presupuesto_id}/estado", json={"estado": "RECHAZADO", "motivo": motivo}
    )


def test_el_contratista_edita_su_presupuesto_sin_poder_cambiar_de_empresa(
    client, loguear_contratista, crear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    otra = crear_contratista(nombre_empresa="Otra")
    presupuesto = _cargar(client, reclamo, ficha).json()
    assert presupuesto["editable"] is True

    respuesta = client.put(
        f"/presupuestos/{presupuesto['id']}",
        json={
            "contratista_id": otra.id,
            "items": [{"descripcion": "Membrana", "cantidad": "2", "costo_unitario": "800"}],
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["contratista_id"] == ficha.id
    assert float(respuesta.json()["monto"]) == 1600


def test_no_edita_el_presupuesto_de_otro(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ajeno = _cargar(client, reclamo, loguear_contratista("Ajena")).json()
    ficha = loguear_contratista("Propia")

    respuesta = client.put(
        f"/presupuestos/{ajeno['id']}", json={"contratista_id": ficha.id, "items": ITEMS}
    )

    assert respuesta.status_code == 403


def test_no_carga_un_segundo_presupuesto_mientras_el_primero_esta_en_evaluacion(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    _cargar(client, reclamo, ficha)

    assert _cargar(client, reclamo, ficha).status_code == 409


def test_rechazado_se_avisa_no_se_edita_y_se_reenvia_como_nuevo_intento(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    primero = _cargar(client, reclamo, ficha).json()

    rechazado = _rechazar(client, primero["id"]).json()

    assert reclamo.estado is EstadoReclamo.PENDIENTE_PRESUPUESTO
    assert rechazado["motivo_rechazo"] == "Precio fuera de mercado"
    assert rechazado["reenviable"] is True
    assert rechazado["editable"] is False
    assert "Precio fuera de mercado" in sin_efectos_externos[0]
    assert (
        client.put(
            f"/presupuestos/{primero['id']}", json={"contratista_id": ficha.id, "items": ITEMS}
        ).status_code
        == 409
    )

    segundo = _cargar(client, reclamo, ficha)

    assert segundo.status_code == 201
    assert segundo.json()["intento"] == 2
    assert reclamo.estado is EstadoReclamo.EN_EVALUACION
    assert client.get(f"/presupuestos/{primero['id']}").json()["reenviable"] is False


def test_mis_solicitudes_muestra_el_ultimo_envio(
    client, db, loguear_contratista, crear_reclamo
):
    from models.solicitud_presupuesto import SolicitudPresupuesto

    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=ficha.id))
    primero = _cargar(client, reclamo, ficha).json()
    _rechazar(client, primero["id"])

    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["presupuesto_estado"] == "RECHAZADO"
    assert solicitud["puede_reenviar"] is True

    segundo = _cargar(client, reclamo, ficha).json()

    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["presupuesto_id"] == segundo["id"]
    assert solicitud["intentos"] == 2
    assert solicitud["puede_editar"] is True
    assert solicitud["puede_reenviar"] is False


def test_no_se_reenvia_si_ya_se_aprobo_otra_oferta(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ganador = _cargar(client, reclamo, loguear_contratista("Ganadora")).json()
    perdedor = loguear_contratista("Perdedora")
    rechazado = _cargar(client, reclamo, perdedor).json()
    _rechazar(client, rechazado["id"])
    client.post(f"/presupuestos/{ganador['id']}/estado", json={"estado": "APROBADO"})

    assert client.get(f"/presupuestos/{rechazado['id']}").json()["reenviable"] is False
    assert _cargar(client, reclamo, perdedor).status_code == 409


def test_queda_convocado_si_le_llega_el_mail_aunque_falle_el_whatsapp(
    client, monkeypatch, crear_contratista, crear_reclamo
):
    import api.reclamos

    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = crear_contratista()
    monkeypatch.setattr(
        api.reclamos, "enviar_mensaje", lambda telefono, texto: {"error": "token inválido"}
    )
    monkeypatch.setattr(api.reclamos, "_email_del_contratista", lambda db, c: "c@test.local")
    monkeypatch.setattr(api.reclamos, "enviar_solicitud_presupuesto", lambda *args: True)

    respuesta = client.post(
        f"/reclamos/{reclamo.id}/notificar-contratistas", json={"contratista_ids": [ficha.id]}
    )

    assert respuesta.json()["enviados"] == 1
    [solicitud] = client.get(f"/reclamos/{reclamo.id}/solicitudes-presupuesto").json()
    assert solicitud["contratista_id"] == ficha.id


def test_mi_presupuesto_devuelve_el_ultimo_envio_del_contratista(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    _cargar(client, reclamo, loguear_contratista("Otra"))
    ficha = loguear_contratista()
    assert client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json() is None

    primero = _cargar(client, reclamo, ficha).json()
    _rechazar(client, primero["id"])
    ultimo = client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json()
    assert ultimo["id"] == primero["id"]
    assert ultimo["reenviable"] is True

    segundo = _cargar(client, reclamo, ficha).json()
    ultimo = client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json()
    assert ultimo["id"] == segundo["id"]
    assert ultimo["editable"] is True
