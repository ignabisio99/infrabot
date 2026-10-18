import pytest

import api.presupuestos
import services.avisos_presupuesto
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
        services.avisos_presupuesto, "enviar_mensaje", lambda telefono, texto: avisos.append(texto)
    )
    for envio in (
        "enviar_aprobado_presupuesto",
        "enviar_rechazo_presupuesto",
        "enviar_ajustes_presupuesto",
        "enviar_no_seleccionado_presupuesto",
        "enviar_reclamo_cancelado_presupuesto",
    ):
        monkeypatch.setattr(
            services.avisos_presupuesto, envio, lambda *args: avisos.append(args)
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


def _decidir(client, presupuesto_id, estado, motivo=None):
    return client.post(
        f"/presupuestos/{presupuesto_id}/estado", json={"estado": estado, "motivo": motivo}
    )


def _rechazar(client, presupuesto_id, motivo="Precio fuera de mercado"):
    return _decidir(client, presupuesto_id, "RECHAZADO", motivo)


def _pedir_ajustes(client, presupuesto_id, motivo="Falta el disyuntor"):
    return _decidir(client, presupuesto_id, "AJUSTES_SOLICITADOS", motivo)


def _editar(client, presupuesto, ficha, costo="800"):
    return client.put(
        f"/presupuestos/{presupuesto['id']}",
        json={
            "contratista_id": ficha.id,
            "items": [{"descripcion": "Membrana", "cantidad": "2", "costo_unitario": costo}],
        },
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


def test_rechazado_cierra_la_oferta_pero_puede_mandar_otra(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()

    rechazado = _rechazar(client, presupuesto["id"]).json()

    assert reclamo.estado is EstadoReclamo.PENDIENTE_PRESUPUESTO
    assert rechazado["motivo_estado"] == "Precio fuera de mercado"
    assert rechazado["editable"] is False
    assert "Precio fuera de mercado" in sin_efectos_externos[0]
    assert f"/portal/reclamos/{reclamo.id}/presupuestar" in sin_efectos_externos[0]
    assert _editar(client, presupuesto, ficha).status_code == 409

    nueva = _cargar(client, reclamo, ficha)

    assert nueva.status_code == 201
    assert nueva.json()["id"] != presupuesto["id"]
    assert nueva.json()["version"] == 1
    assert reclamo.estado is EstadoReclamo.EN_EVALUACION
    assert client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json()["id"] == nueva.json()["id"]


def test_otro_contratista_puede_ofertar_tras_un_rechazo_ajeno(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    rechazado = _cargar(client, reclamo, loguear_contratista("Rechazada")).json()
    _rechazar(client, rechazado["id"])

    assert _cargar(client, reclamo, loguear_contratista("Otra")).status_code == 201


def test_pedir_ajustes_exige_motivo(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    presupuesto = _cargar(client, reclamo, loguear_contratista()).json()

    assert _pedir_ajustes(client, presupuesto["id"], motivo="  ").status_code == 422


def test_ajustes_solicitados_se_corrigen_en_una_version_nueva(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()

    pedido = _pedir_ajustes(client, presupuesto["id"]).json()

    assert pedido["estado"] == "AJUSTES_SOLICITADOS"
    assert pedido["motivo_estado"] == "Falta el disyuntor"
    assert pedido["editable"] is True
    assert reclamo.estado is EstadoReclamo.EN_EVALUACION
    assert "Falta el disyuntor" in sin_efectos_externos[0]
    assert f"/portal/reclamos/{reclamo.id}/presupuestar" in sin_efectos_externos[0]
    assert _cargar(client, reclamo, ficha).status_code == 409

    corregido = _editar(client, presupuesto, ficha).json()

    assert corregido["id"] == presupuesto["id"]
    assert corregido["estado"] == "RECIBIDO"
    assert corregido["version"] == 2
    assert float(corregido["monto"]) == 1600
    [anterior] = client.get(f"/presupuestos/{presupuesto['id']}/versiones").json()
    assert anterior["numero"] == 1
    assert float(anterior["monto"]) == 2000
    assert anterior["ajustes_solicitados"] == "Falta el disyuntor"


def test_editar_por_su_cuenta_tambien_archiva_la_version(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()

    _editar(client, presupuesto, ficha, costo="800")
    tercera = _editar(client, presupuesto, ficha, costo="700").json()

    assert tercera["version"] == 3
    versiones = client.get(f"/presupuestos/{presupuesto['id']}/versiones").json()
    assert [float(v["monto"]) for v in versiones] == [2000, 1600]
    assert all(v["ajustes_solicitados"] is None for v in versiones)
    assert versiones[1]["fecha_envio"] == versiones[0]["fecha_reemplazo"]


def test_las_versiones_no_las_ve_otro_contratista(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ajeno = _cargar(client, reclamo, loguear_contratista("Ajena")).json()
    loguear_contratista("Propia")

    assert client.get(f"/presupuestos/{ajeno['id']}/versiones").status_code == 403


def test_el_admin_no_vuelve_a_recibido_a_mano(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    presupuesto = _cargar(client, reclamo, loguear_contratista()).json()
    pedido = _pedir_ajustes(client, presupuesto["id"]).json()

    assert pedido["estados_posibles"] == ["RECHAZADO"]
    assert _decidir(client, presupuesto["id"], "RECIBIDO").status_code == 409


def test_aprobar_otra_oferta_deja_sin_seleccionar_la_que_esperaba_ajustes(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    en_ajustes = _cargar(client, reclamo, loguear_contratista("Ajustes")).json()
    ganador = _cargar(client, reclamo, loguear_contratista("Ganadora")).json()
    _pedir_ajustes(client, en_ajustes["id"])

    _decidir(client, ganador["id"], "APROBADO")

    assert client.get(f"/presupuestos/{en_ajustes['id']}").status_code == 403
    loguear_contratista("Ajustes")
    perdedor = client.get(f"/presupuestos/{en_ajustes['id']}").json()
    assert perdedor["estado"] == "NO_SELECCIONADO"
    assert perdedor["editable"] is False


def test_mis_solicitudes_muestra_la_version_y_si_puede_editar(
    client, db, loguear_contratista, crear_reclamo
):
    from models.solicitud_presupuesto import SolicitudPresupuesto

    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=ficha.id))
    presupuesto = _cargar(client, reclamo, ficha).json()
    _pedir_ajustes(client, presupuesto["id"])

    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["presupuesto_estado"] == "AJUSTES_SOLICITADOS"
    assert solicitud["puede_editar"] is True

    _editar(client, presupuesto, ficha)
    _rechazar(client, presupuesto["id"])

    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["version"] == 2
    assert solicitud["presupuesto_estado"] == "RECHAZADO"
    assert solicitud["puede_editar"] is False
    assert solicitud["puede_ofertar"] is True


def test_mi_presupuesto_devuelve_la_oferta_del_contratista(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    _cargar(client, reclamo, loguear_contratista("Otra"))
    ficha = loguear_contratista()
    assert client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json() is None

    presupuesto = _cargar(client, reclamo, ficha).json()
    _pedir_ajustes(client, presupuesto["id"])

    mio = client.get(f"/contratistas/mi-presupuesto/{reclamo.id}").json()
    assert mio["id"] == presupuesto["id"]
    assert mio["estado"] == "AJUSTES_SOLICITADOS"


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



def test_guardar_sin_cambios_no_crea_una_version(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()

    igual = _editar(client, presupuesto, ficha, costo="1000.00")

    assert igual.status_code == 200
    assert igual.json()["version"] == 1
    assert client.get(f"/presupuestos/{presupuesto['id']}/versiones").json() == []


def test_no_responde_un_pedido_de_ajustes_sin_cambios(client, loguear_contratista, crear_reclamo):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()
    _pedir_ajustes(client, presupuesto["id"])

    assert _editar(client, presupuesto, ficha, costo="1000").status_code == 422
    assert client.get(f"/presupuestos/{presupuesto['id']}").json()["estado"] == "AJUSTES_SOLICITADOS"


def test_se_avisa_a_las_ofertas_que_quedan_sin_seleccionar(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    en_ajustes = _cargar(client, reclamo, loguear_contratista("Ajustes")).json()
    ganador = _cargar(client, reclamo, loguear_contratista("Ganadora")).json()
    _pedir_ajustes(client, en_ajustes["id"])
    sin_efectos_externos.clear()

    _decidir(client, ganador["id"], "APROBADO")

    assert any("no fue seleccionado" in str(aviso) for aviso in sin_efectos_externos)
    assert ("ajustes@test.local", reclamo.id, reclamo.nombre_escuela) in sin_efectos_externos


def test_se_avisa_por_mail_al_ganador(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ganador = _cargar(client, reclamo, loguear_contratista("Ganadora")).json()

    _decidir(client, ganador["id"], "APROBADO")

    [mail] = sin_efectos_externos
    assert mail[:4] == ("ganadora@test.local", reclamo.id, reclamo.nombre_escuela, reclamo.ubicacion)
    assert mail[4].endswith("/portal/presupuestos")


def test_cancelar_el_reclamo_avisa_a_las_ofertas_en_carrera(
    client, loguear_contratista, crear_reclamo, sin_efectos_externos
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    presupuesto = _cargar(client, reclamo, loguear_contratista()).json()
    _pedir_ajustes(client, presupuesto["id"])
    sin_efectos_externos.clear()

    client.post(
        f"/reclamos/{reclamo.id}/estado", json={"estado": "CANCELADO", "motivo": "Se resolvió"}
    )

    assert "se canceló" in sin_efectos_externos[0]
    assert sin_efectos_externos[1][3] == "Se resolvió"
    cancelado = client.get(f"/presupuestos/{presupuesto['id']}").json()
    assert cancelado["editable"] is False
    assert cancelado["reclamo"]["estado"] == "CANCELADO"


def test_sin_seleccionar_puede_volver_a_ofertar_si_se_reabre_la_convocatoria(
    client, db, loguear_contratista, crear_reclamo
):
    from models.solicitud_presupuesto import SolicitudPresupuesto

    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista("Perdedora")
    db.add(SolicitudPresupuesto(reclamo_id=reclamo.id, contratista_id=ficha.id))
    _cargar(client, reclamo, ficha)
    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["puede_ofertar"] is False

    ganador = _cargar(client, reclamo, loguear_contratista("Ganadora")).json()
    _decidir(client, ganador["id"], "APROBADO")
    reclamo.estado = EstadoReclamo.PENDIENTE_PRESUPUESTO
    db.flush()

    loguear_contratista("Perdedora")
    [solicitud] = client.get("/contratistas/mis-solicitudes").json()
    assert solicitud["presupuesto_estado"] == "NO_SELECCIONADO"
    assert solicitud["puede_ofertar"] is True


def test_la_campanita_cuenta_las_versiones_corregidas_hasta_que_se_decide(
    client, loguear_contratista, crear_reclamo
):
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    ficha = loguear_contratista()
    presupuesto = _cargar(client, reclamo, ficha).json()
    _pedir_ajustes(client, presupuesto["id"])
    _editar(client, presupuesto, ficha)

    assert client.get("/notificaciones/conteo").json()["versiones_por_decidir"] == 1

    _rechazar(client, presupuesto["id"])

    assert client.get("/notificaciones/conteo").json()["versiones_por_decidir"] == 0
