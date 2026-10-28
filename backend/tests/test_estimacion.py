from datetime import date, datetime, timezone
from decimal import Decimal

from core.ai.factory import reset_llm_provider_cache
from models.indice_inflacion import IndiceInflacion
from models.reclamo import EstadoReclamo, PrioridadReclamo
from models.referencia_costo import ReferenciaCosto
from schemas.ai import EstimacionPreliminarOut
from services.ai.estimacion import (
    _alinear_confianza_en_justificacion,
    _confianza_estimacion,
    _justificacion_coherente,
    _justificacion_estimacion,
    _promedio_ponderado,
    _validar_desvio,
    generar_estimacion,
)
from services.ai.historicos import ReferenciaAjustada


def _ref(monto, similitud, id_=1):
    return ReferenciaAjustada(
        id=id_,
        categoria="Electricidad",
        descripcion="tablero eléctrico",
        monto_original=Decimal(str(monto)),
        monto_ajustado=Decimal(str(monto)),
        similitud=similitud,
        fecha_referencia="2026-01-01",
        meta_inflacion={},
    )


def test_confianza_no_se_aplana_a_045_si_hay_desvio():
    validacion = {"motivo": "desvio_vs_historicos", "desvio": 0.25}
    confianza = _confianza_estimacion(0.7, 0.7, validacion)
    assert confianza != 0.45
    assert 0.40 < confianza < 0.70


def test_confianza_sin_referencias_queda_baja():
    validacion = {"motivo": "sin_referencias", "desvio": None, "promedio_refs": None}
    confianza = _confianza_estimacion(0.25, 0.8, validacion)
    assert confianza <= 0.30
    assert confianza != 0.45


def test_justificacion_usa_el_texto_del_llm():
    texto = _justificacion_estimacion(
        {"justificacion": "  Anclado a tableros similares.  "},
        [_ref(200_000, 0.8)],
        {"motivo": "ok"},
    )
    assert texto == "Anclado a tableros similares."


def test_justificacion_no_cita_id_interno():
    texto = _justificacion_estimacion(
        {
            "justificacion": (
                "La estimación se basa en el precedente id=12, ajustado por IPC, "
                "que cubre mantenimiento menor."
            )
        },
        [_ref(50000, 0.15, id_=12)],
        {"motivo": "ok"},
    )
    assert "id=12" not in texto
    assert "id = 12" not in texto.lower()
    assert "tablero eléctrico" in texto


def test_justificacion_usa_la_confianza_del_sistema():
    texto = (
        "El monto se ancló al tablero escolar. "
        "La confianza se mantiene en 0.58 debido a la similitud moderada."
    )
    alineado = _alinear_confianza_en_justificacion(texto, 0.49)
    assert "0.58" not in alineado
    assert "49%" in alineado


def test_justificacion_no_dice_solida_si_hay_que_revisar():
    texto = (
        "Se usó el tablero escolar (306666.67 ARS). "
        "La estimación se considera sólida, pues se ajusta dentro del rango de los precedentes históricos."
    )
    alineado = _justificacion_coherente(
        texto,
        materiales=Decimal("113850"),
        mano_obra=Decimal("211313"),
        otros=Decimal("36129"),
        total=Decimal("361292"),
        confianza=0.35,
        validacion={"motivo": "desvio_vs_historicos"},
    )
    assert "sólida" not in alineado.lower()
    assert "dentro del rango" not in alineado.lower()
    assert "113.850" in alineado
    assert "361.292" in alineado
    assert "306.667" in alineado or "306.666" in alineado
    assert "conviene revisarlo" in alineado.lower()


def test_justificacion_sin_llm_explica_falta_de_historicos():
    texto = _justificacion_estimacion({}, [], {"motivo": "sin_referencias"})
    assert "inspección" in texto.lower() or "historicos" in texto.lower() or "históric" in texto.lower()


def test_confianza_ok_refleja_precedentes():
    validacion = {"motivo": "ok", "desvio": 0.05}
    confianza = _confianza_estimacion(0.78, 0.78, validacion)
    assert confianza > 0.65


def test_promedio_ponderado_prioriza_la_ref_parecida():
    refs = [_ref(100_000, 0.9, 1), _ref(500_000, 0.1, 2)]
    promedio = _promedio_ponderado(refs)
    assert abs(promedio - Decimal("140000")) < Decimal("0.01")


def test_validar_desvio_cerca_del_promedio_no_pide_revision():
    refs = [_ref(200_000, 0.8)]
    requiere, validacion = _validar_desvio(Decimal("210000.00"), refs)
    assert requiere is False
    assert validacion["motivo"] == "ok"


def test_validar_desvio_sin_refs_pide_revision():
    requiere, validacion = _validar_desvio(Decimal("100000.00"), [])
    assert requiere is True
    assert validacion["motivo"] == "sin_referencias"


def test_generar_con_precedentes_no_fija_45(db, crear_reclamo, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    reset_llm_provider_cache()
    try:
        db.add(IndiceInflacion(periodo="2026-01", indice=100.0, fuente="test"))
        db.add(
            ReferenciaCosto(
                categoria="Electricidad",
                descripcion="Reparación de tablero eléctrico principal escolar",
                monto_ars=200000,
                fecha_referencia=date(2026, 1, 15),
                fuente="test",
                activo=True,
            )
        )
        db.flush()

        reclamo = crear_reclamo(
            prioridad=PrioridadReclamo.MEDIA,
            estado=EstadoReclamo.PENDIENTE_PRESUPUESTO,
            fecha_creacion=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        reclamo.categoria = "Electricidad"
        reclamo.descripcion = "Se quemó el tablero eléctrico principal de la escuela"
        db.flush()
        estimacion = generar_estimacion(db, reclamo, transicionar=False)

        assert estimacion.confianza != 0.45
        assert estimacion.confianza > 0.50
        assert estimacion.requiere_revision is False
        assert estimacion.total > 0
        out = EstimacionPreliminarOut.model_validate(estimacion)
        assert out.sin_precedentes is False
        assert out.justificacion
        assert "mock" in out.justificacion.lower() or "precedente" in out.justificacion.lower()
    finally:
        reset_llm_provider_cache()


def test_generar_sin_precedentes_confianza_baja_no_45(db, crear_reclamo, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    reset_llm_provider_cache()
    try:
        reclamo = crear_reclamo(
            prioridad=PrioridadReclamo.ALTA,
            estado=EstadoReclamo.PENDIENTE_PRESUPUESTO,
        )
        reclamo.categoria = "Gas"
        reclamo.descripcion = "Hay olor a gas en la cocina del comedor"
        db.flush()
        estimacion = generar_estimacion(db, reclamo, transicionar=False)

        assert estimacion.requiere_revision is True
        assert estimacion.total > 0
        assert estimacion.materiales > 0
        assert estimacion.confianza <= 0.30
        assert estimacion.confianza != 0.45
        out = EstimacionPreliminarOut.model_validate(estimacion)
        assert out.sin_precedentes is True
        assert out.justificacion
        assert "sin precedentes históricos" in out.justificacion.lower()
    finally:
        reset_llm_provider_cache()
