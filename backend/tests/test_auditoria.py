from decimal import Decimal

from services.ai.auditoria import RecomendacionAuditoria, _recomendacion_por_desvio
from services.ai.estimacion import sirve_como_ancla_auditoria
from types import SimpleNamespace


def test_mas_barato_se_aprueba():
    rec, abs_, pct = _recomendacion_por_desvio(
        Decimal("80000"), Decimal("100000"), Decimal("0.05"), Decimal("0.20")
    )
    assert rec is RecomendacionAuditoria.APROBAR
    assert abs_ < 0
    assert pct < 0


def test_mucho_mas_caro_se_rechaza():
    rec, abs_, pct = _recomendacion_por_desvio(
        Decimal("200000"), Decimal("100000"), Decimal("0.05"), Decimal("0.20")
    )
    assert rec is RecomendacionAuditoria.RECHAZAR
    assert abs_ > 0
    assert pct == Decimal("1.0000")


def test_un_poco_mas_caro_se_revisa():
    rec, _, pct = _recomendacion_por_desvio(
        Decimal("110000"), Decimal("100000"), Decimal("0.05"), Decimal("0.20")
    )
    assert rec is RecomendacionAuditoria.REVISAR
    assert pct == Decimal("0.1000")


def test_estimacion_sin_precedentes_no_es_ancla():
    est = SimpleNamespace(
        total=Decimal("0"),
        confianza=0.0,
        detalle='{"validacion": {"motivo": "sin_referencias"}, "referencias_ids": []}',
    )
    assert sirve_como_ancla_auditoria(est) is False
    assert sirve_como_ancla_auditoria(None) is False


def test_estimacion_con_total_y_refs_es_ancla():
    est = SimpleNamespace(
        total=Decimal("150000.00"),
        confianza=0.7,
        detalle='{"validacion": {"motivo": "ok"}, "referencias_ids": [1]}',
    )
    assert sirve_como_ancla_auditoria(est) is True
