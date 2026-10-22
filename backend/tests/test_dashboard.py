"""Tests de las agregaciones del dashboard.

Las funciones internas se prueban pasándoles `ahora` explícito en vez de dejarlas leer el
reloj: así los cortes por fecha (mes, ventanas de 30 días, umbral de estancado) quedan
fijos y los tests no cambian de resultado según el día en que se corren.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from api.dashboard import (
    ART,
    DIAS_SIN_MOVIMIENTO,
    ESTADOS_ABIERTOS,
    MAX_ESTANCADOS,
    Filtros,
    PeriodoDias,
    _cantidad_de_meses,
    _clave_mes,
    _conteo_por_estado,
    _dias_promedio_resolucion,
    _estancados,
    _finalizados,
    _ingresados,
    _kpis,
    _meses_de_la_serie,
    _monto_aprobado,
    _serie_mensual,
    _tiempo_por_etapa,
)
from conftest import UTC
from models.reclamo import EstadoReclamo, PrioridadReclamo
from schemas.dashboard import EtapaFlujo
from models.visita import EstadoVisita

AHORA = datetime(2026, 9, 15, 12, 0, tzinfo=ART)
INICIO_MES = datetime(2026, 9, 1, tzinfo=ART)
DESDE_SIEMPRE = datetime(2000, 1, 1, tzinfo=ART)


# --- Helpers de fecha ------------------------------------------------------------------


class TestMesesDeLaSerie:
    def test_devuelve_los_ultimos_meses_del_mas_viejo_al_mas_nuevo(self):
        desde, claves = _meses_de_la_serie(datetime(2026, 9, 15, tzinfo=ART), 3)

        assert claves == ["2026-07", "2026-08", "2026-09"]
        assert desde == datetime(2026, 7, 1, tzinfo=ART)

    def test_cruza_el_cambio_de_anio(self):
        desde, claves = _meses_de_la_serie(datetime(2026, 2, 10, tzinfo=ART), 4)

        assert claves == ["2025-11", "2025-12", "2026-01", "2026-02"]
        assert desde == datetime(2025, 11, 1, tzinfo=ART)

    def test_desde_arranca_al_inicio_del_mes_en_hora_local(self):
        desde, _ = _meses_de_la_serie(datetime(2026, 9, 15, 23, 30, tzinfo=ART), 6)

        assert desde.utcoffset() == timedelta(hours=-3)
        assert (desde.year, desde.month, desde.day, desde.hour) == (2026, 4, 1, 0)

    def test_clave_mes_rellena_con_ceros(self):
        assert _clave_mes(datetime(2026, 3, 7, tzinfo=ART)) == "2026-03"

    def test_estados_abiertos_es_el_enum_menos_los_finales(self):
        assert EstadoReclamo.DESIERTO in ESTADOS_ABIERTOS
        assert not {
            EstadoReclamo.FINALIZADO,
            EstadoReclamo.RECHAZADO,
            EstadoReclamo.CANCELADO,
        } & set(ESTADOS_ABIERTOS)


# --- Monto aprobado --------------------------------------------------------------------


class TestMontoAprobado:
    def test_suma_cantidad_por_costo_unitario_de_todos_los_items(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo,
            items=[(2, 1000), (3, 500)],
            fecha_aprobacion=AHORA - timedelta(days=3),
        )

        assert _monto_aprobado(db, INICIO_MES) == Decimal("3500.00")

    def test_varios_items_no_multiplican_el_total(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        """Con un solo asiento de aprobación el join no debe repetir los ítems."""
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo,
            items=[(1, 100)] * 5,
            fecha_aprobacion=AHORA - timedelta(days=1),
        )

        assert _monto_aprobado(db, INICIO_MES) == Decimal("500.00")

    def test_ignora_lo_aprobado_antes_del_corte(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo,
            items=[(1, 9999)],
            fecha_aprobacion=INICIO_MES - timedelta(minutes=1),
        )

        assert _monto_aprobado(db, INICIO_MES) == 0

    def test_cuenta_por_fecha_de_aprobacion_y_no_por_fecha_del_presupuesto(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        """El presupuesto se cargó el mes pasado pero se aprobó este: cuenta este mes."""
        reclamo = crear_reclamo(
            estado=EstadoReclamo.APROBADO,
            fecha_creacion=INICIO_MES - timedelta(days=20),
        )
        presupuesto = crear_presupuesto_aprobado(
            reclamo,
            items=[(1, 4000)],
            fecha_aprobacion=AHORA - timedelta(days=2),
        )
        presupuesto.fecha = INICIO_MES - timedelta(days=15)
        db.flush()

        assert _monto_aprobado(db, INICIO_MES) == Decimal("4000.00")

    def test_sin_aprobaciones_devuelve_cero(self, db):
        assert _monto_aprobado(db, INICIO_MES) == 0


# --- Días promedio de resolución -------------------------------------------------------


class TestDiasPromedioResolucion:
    def test_sin_reclamos_finalizados_devuelve_none(self, db, crear_reclamo):
        crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)

        assert _dias_promedio_resolucion(db, DESDE_SIEMPRE) is None

    def test_mide_desde_la_creacion_hasta_el_asiento_de_finalizado(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO,
            fecha_creacion=AHORA - timedelta(days=10),
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=2))

        assert _dias_promedio_resolucion(db, DESDE_SIEMPRE) == 8.0

    def test_promedia_entre_los_finalizados(self, db, crear_reclamo, crear_historial):
        rapido = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=6)
        )
        crear_historial(rapido, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=2))

        lento = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=20)
        )
        crear_historial(lento, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=4))

        # (4 + 16) / 2
        assert _dias_promedio_resolucion(db, DESDE_SIEMPRE) == 10.0

    def test_toma_la_ultima_finalizacion_de_un_reclamo_reabierto(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=30)
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=25))
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=10))

        assert _dias_promedio_resolucion(db, DESDE_SIEMPRE) == 20.0

    def test_un_reclamo_reabierto_cuenta_en_el_rango_de_su_primera_finalizacion(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=50)
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=40))
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=5))

        anterior = (AHORA - timedelta(days=60), AHORA - timedelta(days=30))
        assert _dias_promedio_resolucion(db, *anterior) == 10.0
        assert _finalizados(db, *anterior) == 1
        assert _dias_promedio_resolucion(db, AHORA - timedelta(days=30)) == 45.0

    def test_solo_promedia_los_finalizados_dentro_del_rango(
        self, db, crear_reclamo, crear_historial
    ):
        adentro = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=10)
        )
        crear_historial(adentro, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=5))

        afuera = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=100)
        )
        crear_historial(afuera, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=40))

        assert _dias_promedio_resolucion(db, AHORA - timedelta(days=30)) == 5.0
        assert (
            _dias_promedio_resolucion(db, AHORA - timedelta(days=60), AHORA - timedelta(days=30))
            == 60.0
        )


# --- Reclamos estancados ---------------------------------------------------------------


class TestEstancados:
    def test_usa_la_fecha_de_creacion_cuando_no_hay_historial(self, db, crear_reclamo):
        crear_reclamo(
            estado=EstadoReclamo.PENDIENTE_PRESUPUESTO,
            fecha_creacion=AHORA - timedelta(days=10),
        )

        total, filas = _estancados(db, AHORA)

        assert total == 1
        assert filas[0].dias_sin_movimiento == 10

    def test_usa_el_ultimo_asiento_del_historial(self, db, crear_reclamo, crear_historial):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.EN_EJECUCION,
            fecha_creacion=AHORA - timedelta(days=40),
        )
        crear_historial(reclamo, EstadoReclamo.PENDIENTE_PRESUPUESTO, AHORA - timedelta(days=30))
        crear_historial(reclamo, EstadoReclamo.EN_EJECUCION, AHORA - timedelta(days=9))

        total, filas = _estancados(db, AHORA)

        assert total == 1
        assert filas[0].dias_sin_movimiento == 9

    def test_no_lista_al_que_se_movio_dentro_del_umbral(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.EN_EJECUCION,
            fecha_creacion=AHORA - timedelta(days=40),
        )
        crear_historial(reclamo, EstadoReclamo.EN_EJECUCION, AHORA - timedelta(days=2))

        assert _estancados(db, AHORA) == (0, [])

    def test_excluye_los_estados_finales(self, db, crear_reclamo):
        for estado in (
            EstadoReclamo.FINALIZADO,
            EstadoReclamo.RECHAZADO,
            EstadoReclamo.CANCELADO,
        ):
            crear_reclamo(estado=estado, fecha_creacion=AHORA - timedelta(days=90))

        assert _estancados(db, AHORA) == (0, [])

    def test_incluye_desierto_porque_sigue_abierto(self, db, crear_reclamo):
        crear_reclamo(
            estado=EstadoReclamo.DESIERTO, fecha_creacion=AHORA - timedelta(days=20)
        )

        total, _ = _estancados(db, AHORA)

        assert total == 1

    def test_redondea_los_dias_hacia_arriba(self, db, crear_reclamo):
        """El umbral se anuncia como "más de 7 días": 7.6 tiene que leerse 8, no 7."""
        crear_reclamo(
            estado=EstadoReclamo.PENDIENTE_REVISION,
            fecha_creacion=AHORA - timedelta(days=7.6),
        )

        _, filas = _estancados(db, AHORA)

        assert filas[0].dias_sin_movimiento == 8

    def test_recorta_la_lista_pero_devuelve_el_total(self, db, crear_reclamo):
        cantidad = MAX_ESTANCADOS + 4
        for i in range(cantidad):
            crear_reclamo(
                estado=EstadoReclamo.PENDIENTE_PRESUPUESTO,
                nombre_escuela=f"Escuela {i}",
                fecha_creacion=AHORA - timedelta(days=DIAS_SIN_MOVIMIENTO + 1 + i),
            )

        total, filas = _estancados(db, AHORA)

        assert total == cantidad
        assert len(filas) == MAX_ESTANCADOS

    def test_ordena_del_mas_viejo_al_mas_nuevo(self, db, crear_reclamo):
        for i, dias in enumerate((8, 30, 15)):
            crear_reclamo(
                estado=EstadoReclamo.PENDIENTE_PRESUPUESTO,
                nombre_escuela=f"Escuela {i}",
                fecha_creacion=AHORA - timedelta(days=dias),
            )

        _, filas = _estancados(db, AHORA)

        assert [f.dias_sin_movimiento for f in filas] == [30, 15, 8]


# --- Serie mensual ---------------------------------------------------------------------


class TestSerieMensual:
    def test_devuelve_una_entrada_por_mes_con_los_meses_vacios_en_cero(
        self, db, crear_reclamo
    ):
        crear_reclamo(fecha_creacion=datetime(2026, 7, 10, tzinfo=ART))

        serie = _serie_mensual(db, AHORA)

        assert [p.mes for p in serie] == [
            "2026-04",
            "2026-05",
            "2026-06",
            "2026-07",
            "2026-08",
            "2026-09",
        ]
        assert [p.ingresados for p in serie] == [0, 0, 0, 1, 0, 0]

    def test_agrupa_en_hora_local_y_no_en_utc(self, db, crear_reclamo):
        """01:00Z del 1/9 son las 22:00 del 31/8 en ART: el reclamo es de agosto."""
        crear_reclamo(fecha_creacion=datetime(2026, 9, 1, 1, 0, tzinfo=UTC))

        serie = {p.mes: p.ingresados for p in _serie_mensual(db, AHORA)}

        assert serie["2026-08"] == 1
        assert serie["2026-09"] == 0

    def test_cuenta_finalizados_por_la_fecha_del_asiento(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO,
            fecha_creacion=datetime(2026, 6, 5, tzinfo=ART),
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, datetime(2026, 8, 20, tzinfo=ART))

        serie = {p.mes: (p.ingresados, p.finalizados) for p in _serie_mensual(db, AHORA)}

        assert serie["2026-06"] == (1, 0)
        assert serie["2026-08"] == (0, 1)

    def test_no_cuenta_dos_veces_al_reclamo_finalizado_dos_veces_en_el_mes(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO,
            fecha_creacion=datetime(2026, 8, 1, tzinfo=ART),
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, datetime(2026, 8, 10, tzinfo=ART))
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, datetime(2026, 8, 25, tzinfo=ART))

        serie = {p.mes: p.finalizados for p in _serie_mensual(db, AHORA)}

        assert serie["2026-08"] == 1

    def test_suma_el_monto_aprobado_por_mes_de_aprobacion(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo, items=[(2, 500)], fecha_aprobacion=datetime(2026, 7, 3, tzinfo=ART)
        )
        crear_presupuesto_aprobado(
            reclamo, items=[(1, 250)], fecha_aprobacion=datetime(2026, 7, 28, tzinfo=ART)
        )

        serie = {p.mes: p.monto_aprobado for p in _serie_mensual(db, AHORA)}

        assert serie["2026-07"] == Decimal("1250.00")
        assert serie["2026-08"] == 0

    def test_el_periodo_anual_muestra_doce_meses_y_los_cortos_seis(self):
        assert _cantidad_de_meses(PeriodoDias.ANIO) == 12
        assert _cantidad_de_meses(PeriodoDias.TRIMESTRE) == 6
        assert _cantidad_de_meses(PeriodoDias.MES) == 6

    def test_ignora_lo_anterior_a_la_ventana(self, db, crear_reclamo):
        crear_reclamo(fecha_creacion=datetime(2026, 1, 15, tzinfo=ART))

        serie = _serie_mensual(db, AHORA)

        assert sum(p.ingresados for p in serie) == 0


# --- KPIs ------------------------------------------------------------------------------


class TestKpis:
    def _kpis_de(self, db):
        return _kpis(db, AHORA, _conteo_por_estado(db))

    def test_abiertos_excluye_finales_e_incluye_desierto(self, db, crear_reclamo):
        for estado in (
            EstadoReclamo.PENDIENTE_REVISION,
            EstadoReclamo.EN_EVALUACION,
            EstadoReclamo.DESIERTO,
            EstadoReclamo.FINALIZADO,
            EstadoReclamo.RECHAZADO,
            EstadoReclamo.CANCELADO,
        ):
            crear_reclamo(estado=estado)

        kpis = self._kpis_de(db)

        assert kpis.reclamos_abiertos == 3
        assert kpis.pendientes_revision == 1
        assert kpis.en_evaluacion == 1

    def test_ingresados_compara_el_periodo_con_el_anterior(self, db, crear_reclamo):
        for dias in (0, 1, 29):
            crear_reclamo(fecha_creacion=AHORA - timedelta(days=dias))
        for dias in (31, 59):
            crear_reclamo(fecha_creacion=AHORA - timedelta(days=dias))
        crear_reclamo(fecha_creacion=AHORA - timedelta(days=90))

        ingresados = self._kpis_de(db).ingresados

        assert (ingresados.actual, ingresados.anterior) == (3, 2)

    def test_el_periodo_cambia_el_largo_de_las_dos_ventanas(self, db, crear_reclamo):
        for dias in (10, 80, 100, 170, 200):
            crear_reclamo(fecha_creacion=AHORA - timedelta(days=dias))

        ingresados = _kpis(db, AHORA, _conteo_por_estado(db), periodo_dias=90).ingresados

        assert (ingresados.actual, ingresados.anterior) == (2, 2)

    def test_finalizados_compara_el_periodo_con_el_anterior(
        self, db, crear_reclamo, crear_historial
    ):
        for dias in (5, 40, 45):
            reclamo = crear_reclamo(
                estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=80)
            )
            crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=dias))

        finalizados = self._kpis_de(db).finalizados

        assert (finalizados.actual, finalizados.anterior) == (1, 2)

    def test_visitas_cuenta_las_confirmadas_de_los_proximos_7_dias(
        self, db, crear_reclamo, crear_visita
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA)
        crear_visita(reclamo, AHORA + timedelta(days=2))

        assert self._kpis_de(db).visitas_proximos_7_dias == 1

    def test_visitas_ignora_las_de_fuera_de_la_ventana(
        self, db, crear_reclamo, crear_visita
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA)
        crear_visita(reclamo, AHORA + timedelta(days=8))
        crear_visita(reclamo, AHORA - timedelta(days=1))

        assert self._kpis_de(db).visitas_proximos_7_dias == 0

    def test_visitas_ignora_las_que_no_estan_confirmadas(
        self, db, crear_reclamo, crear_visita
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_COORDINACION)
        crear_visita(
            reclamo, AHORA + timedelta(days=2), estado=EstadoVisita.ESPERANDO_ELECCION
        )
        crear_visita(reclamo, AHORA + timedelta(days=3), estado=EstadoVisita.CANCELADA)

        assert self._kpis_de(db).visitas_proximos_7_dias == 0

    def test_monto_aprobado_compara_el_periodo_con_el_anterior(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo, items=[(1, 700)], fecha_aprobacion=AHORA - timedelta(days=1)
        )
        otro = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            otro, items=[(2, 150)], fecha_aprobacion=AHORA - timedelta(days=35)
        )

        monto = self._kpis_de(db).monto_aprobado

        assert monto.actual == Decimal("700.00")
        assert monto.anterior == Decimal("300.00")

    def test_base_vacia_no_rompe(self, db):
        kpis = self._kpis_de(db)

        assert kpis.reclamos_abiertos == 0
        assert kpis.monto_aprobado.actual == 0
        assert kpis.dias_promedio_resolucion.actual is None
        assert kpis.dias_promedio_resolucion.anterior is None


# --- Tiempo por etapa -----------------------------------------------------------------


E = EstadoReclamo
HACE_30 = AHORA - timedelta(days=30)


def _por_etapa(db, desde=HACE_30, hasta=None, filtros=None):
    filas = _tiempo_por_etapa(db, desde, hasta, filtros or Filtros())
    return {fila.etapa: (fila.dias_promedio, fila.reclamos) for fila in filas}


class TestTiempoPorEtapa:
    def _recorrer(self, crear_reclamo, crear_historial, creado_hace, pasos, **campos):
        """Crea un reclamo y su historial. `pasos` son (estado_nuevo, días atrás), en orden."""
        reclamo = crear_reclamo(
            estado=pasos[-1][0], fecha_creacion=AHORA - timedelta(days=creado_hace), **campos
        )
        anterior = None
        for estado, dias in pasos:
            fecha = AHORA - timedelta(days=dias)
            crear_historial(reclamo, estado, fecha, estado_anterior=anterior)
            anterior = estado
        return reclamo

    def test_mide_cada_etapa_desde_el_asiento_anterior(
        self, db, crear_reclamo, crear_historial
    ):
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=20,
            pasos=[
                (E.PENDIENTE_REVISION, 20),
                (E.PENDIENTE_PRESUPUESTO, 18),
                (E.EN_EVALUACION, 12),
                (E.APROBADO, 10),
                (E.EN_EJECUCION, 7),
                (E.FINALIZADO, 2),
            ],
        )

        etapas = _por_etapa(db)

        assert etapas[EtapaFlujo.REVISION] == (2.0, 1)
        assert etapas[EtapaFlujo.PRESUPUESTO] == (8.0, 1)
        assert etapas[EtapaFlujo.EJECUCION] == (8.0, 1)

    def test_promedia_entre_reclamos(self, db, crear_reclamo, crear_historial):
        for revision in (1, 5):
            self._recorrer(
                crear_reclamo,
                crear_historial,
                creado_hace=10,
                pasos=[(E.PENDIENTE_REVISION, 10), (E.PENDIENTE_PRESUPUESTO, 10 - revision)],
            )

        assert _por_etapa(db)[EtapaFlujo.REVISION] == (3.0, 2)

    def test_las_idas_y_vueltas_suman_en_la_misma_etapa(
        self, db, crear_reclamo, crear_historial
    ):
        """Pasar por DESIERTO y volver a pedir presupuesto es un solo reclamo en la etapa."""
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=25,
            pasos=[
                (E.PENDIENTE_REVISION, 25),
                (E.PENDIENTE_PRESUPUESTO, 24),
                (E.DESIERTO, 20),
                (E.PENDIENTE_PRESUPUESTO, 18),
                (E.EN_EVALUACION, 15),
                (E.APROBADO, 12),
            ],
        )

        assert _por_etapa(db)[EtapaFlujo.PRESUPUESTO] == (12.0, 1)

    def test_no_cuenta_la_estadia_en_curso(self, db, crear_reclamo, crear_historial):
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=10,
            pasos=[(E.PENDIENTE_REVISION, 10), (E.PENDIENTE_PRESUPUESTO, 9)],
        )

        etapas = _por_etapa(db)

        assert etapas[EtapaFlujo.REVISION] == (1.0, 1)
        assert etapas[EtapaFlujo.PRESUPUESTO] == (None, 0)

    def test_sin_asiento_inicial_mide_desde_la_creacion(
        self, db, crear_reclamo, crear_historial
    ):
        """Reclamos anteriores al historial: la primera estadía arranca en su creación."""
        reclamo = crear_reclamo(
            estado=E.PENDIENTE_PRESUPUESTO, fecha_creacion=AHORA - timedelta(days=6)
        )
        crear_historial(
            reclamo,
            E.PENDIENTE_PRESUPUESTO,
            AHORA - timedelta(days=2),
            estado_anterior=E.PENDIENTE_REVISION,
        )

        assert _por_etapa(db)[EtapaFlujo.REVISION] == (4.0, 1)

    def test_solo_cuenta_las_estadias_que_terminaron_en_el_rango(
        self, db, crear_reclamo, crear_historial
    ):
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=60,
            pasos=[(E.PENDIENTE_REVISION, 60), (E.PENDIENTE_PRESUPUESTO, 50)],
        )

        assert _por_etapa(db)[EtapaFlujo.REVISION] == (None, 0)
        assert _por_etapa(db, desde=AHORA - timedelta(days=90))[EtapaFlujo.REVISION] == (
            10.0,
            1,
        )

    def test_la_estadia_que_cruza_el_corte_se_mide_desde_su_inicio_real(
        self, db, crear_reclamo, crear_historial
    ):
        """Empezó antes del rango y terminó adentro: cuenta entera, no desde el corte."""
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=40,
            pasos=[
                (E.PENDIENTE_REVISION, 40),
                (E.PENDIENTE_PRESUPUESTO, 35),
                (E.EN_EVALUACION, 10),
            ],
        )

        assert _por_etapa(db)[EtapaFlujo.PRESUPUESTO] == (25.0, 1)

    def test_ignora_las_estadias_en_estados_finales(self, db, crear_reclamo, crear_historial):
        self._recorrer(
            crear_reclamo,
            crear_historial,
            creado_hace=10,
            pasos=[(E.PENDIENTE_REVISION, 10), (E.RECHAZADO, 8)],
        )

        etapas = _por_etapa(db)

        assert etapas[EtapaFlujo.REVISION] == (2.0, 1)
        assert sum(reclamos for _, reclamos in etapas.values()) == 1

    def test_respeta_los_filtros(self, db, crear_reclamo, crear_historial):
        for prioridad, dias in ((PrioridadReclamo.ALTA, 1), (PrioridadReclamo.BAJA, 7)):
            self._recorrer(
                crear_reclamo,
                crear_historial,
                creado_hace=10,
                pasos=[(E.PENDIENTE_REVISION, 10), (E.PENDIENTE_PRESUPUESTO, 10 - dias)],
                prioridad=prioridad,
            )

        etapas = _por_etapa(db, filtros=Filtros(prioridad=PrioridadReclamo.ALTA))

        assert etapas[EtapaFlujo.REVISION] == (1.0, 1)

    def test_devuelve_las_tres_etapas_aunque_no_haya_datos(self, db):
        assert _por_etapa(db) == {etapa: (None, 0) for etapa in EtapaFlujo}


# --- Filtros --------------------------------------------------------------------------


class TestFiltros:
    ALTA = Filtros(prioridad=PrioridadReclamo.ALTA)

    def test_conteo_por_estado_respeta_la_prioridad(self, db, crear_reclamo):
        crear_reclamo(prioridad=PrioridadReclamo.ALTA)
        crear_reclamo(prioridad=PrioridadReclamo.BAJA)

        assert _conteo_por_estado(db, self.ALTA) == {EstadoReclamo.PENDIENTE_REVISION: 1}

    def test_ingresados_respeta_la_categoria(self, db, crear_reclamo):
        crear_reclamo(categoria="Gas", fecha_creacion=AHORA - timedelta(days=1))
        crear_reclamo(categoria="Techos", fecha_creacion=AHORA - timedelta(days=1))

        desde = AHORA - timedelta(days=30)

        assert _ingresados(db, desde, filtros=Filtros(categoria="Gas")) == 1
        assert _ingresados(db, desde) == 2

    def test_combina_prioridad_y_categoria(self, db, crear_reclamo):
        crear_reclamo(prioridad=PrioridadReclamo.ALTA, categoria="Gas")
        crear_reclamo(prioridad=PrioridadReclamo.ALTA, categoria="Techos")
        crear_reclamo(prioridad=PrioridadReclamo.BAJA, categoria="Gas")

        filtros = Filtros(prioridad=PrioridadReclamo.ALTA, categoria="Gas")

        assert sum(_conteo_por_estado(db, filtros).values()) == 1

    def test_finalizados_respeta_la_prioridad(self, db, crear_reclamo, crear_historial):
        for prioridad in (PrioridadReclamo.ALTA, PrioridadReclamo.BAJA):
            reclamo = crear_reclamo(estado=EstadoReclamo.FINALIZADO, prioridad=prioridad)
            crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=1))

        assert _finalizados(db, AHORA - timedelta(days=30), filtros=self.ALTA) == 1

    def test_monto_aprobado_respeta_la_prioridad_del_reclamo(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        for prioridad, monto in ((PrioridadReclamo.ALTA, 100), (PrioridadReclamo.BAJA, 900)):
            reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO, prioridad=prioridad)
            crear_presupuesto_aprobado(
                reclamo, items=[(1, monto)], fecha_aprobacion=AHORA - timedelta(days=1)
            )

        assert _monto_aprobado(db, INICIO_MES, filtros=self.ALTA) == Decimal("100.00")

    def test_estancados_respeta_la_prioridad(self, db, crear_reclamo):
        for prioridad in (PrioridadReclamo.ALTA, PrioridadReclamo.BAJA):
            crear_reclamo(prioridad=prioridad, fecha_creacion=AHORA - timedelta(days=20))

        total, filas = _estancados(db, AHORA, self.ALTA)

        assert total == 1
        assert filas[0].prioridad == PrioridadReclamo.ALTA

    def test_visitas_respeta_la_prioridad(self, db, crear_reclamo, crear_visita):
        for prioridad in (PrioridadReclamo.ALTA, PrioridadReclamo.BAJA):
            reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA, prioridad=prioridad)
            crear_visita(reclamo, AHORA + timedelta(days=2))

        kpis = _kpis(db, AHORA, _conteo_por_estado(db, self.ALTA), filtros=self.ALTA)

        assert kpis.visitas_proximos_7_dias == 1

    def test_serie_mensual_respeta_la_prioridad(self, db, crear_reclamo):
        for prioridad in (PrioridadReclamo.ALTA, PrioridadReclamo.BAJA):
            crear_reclamo(prioridad=prioridad, fecha_creacion=datetime(2026, 8, 5, tzinfo=ART))

        serie = {p.mes: p.ingresados for p in _serie_mensual(db, AHORA, filtros=self.ALTA)}

        assert serie["2026-08"] == 1


# --- Endpoint --------------------------------------------------------------------------


class TestEndpointResumen:
    def test_devuelve_el_resumen_completo(self, client, crear_reclamo):
        crear_reclamo(estado=EstadoReclamo.EN_EVALUACION)

        respuesta = client.get("/dashboard/resumen")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert set(cuerpo) == {
            "periodo_dias",
            "categorias",
            "kpis",
            "por_estado",
            "serie_mensual",
            "tiempo_por_etapa",
            "estados_abiertos",
            "estancados",
            "estancados_total",
            "dias_sin_movimiento_umbral",
        }
        assert cuerpo["dias_sin_movimiento_umbral"] == DIAS_SIN_MOVIMIENTO

    def test_estados_abiertos_viaja_en_la_respuesta(self, client):
        cuerpo = client.get("/dashboard/resumen").json()

        assert cuerpo["estados_abiertos"] == [estado.value for estado in ESTADOS_ABIERTOS]

    def test_por_estado_lista_todos_los_estados_incluso_en_cero(
        self, client, crear_reclamo
    ):
        crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)

        cuerpo = client.get("/dashboard/resumen").json()
        conteos = {fila["estado"]: fila["cantidad"] for fila in cuerpo["por_estado"]}

        assert set(conteos) == {estado.value for estado in EstadoReclamo}
        assert conteos["EN_EJECUCION"] == 1
        assert conteos["FINALIZADO"] == 0

    def test_serie_mensual_trae_los_seis_meses(self, client):
        cuerpo = client.get("/dashboard/resumen").json()

        assert len(cuerpo["serie_mensual"]) == 6
        assert cuerpo["periodo_dias"] == 30

    def test_periodo_anual_trae_doce_meses(self, client):
        cuerpo = client.get("/dashboard/resumen", params={"periodo": 365}).json()

        assert cuerpo["periodo_dias"] == 365
        assert len(cuerpo["serie_mensual"]) == 12

    def test_rechaza_un_periodo_que_no_esta_en_las_opciones(self, client):
        assert client.get("/dashboard/resumen", params={"periodo": 45}).status_code == 422

    def test_kpis_comparativos_traen_actual_y_anterior(self, client):
        kpis = client.get("/dashboard/resumen").json()["kpis"]

        for campo in ("ingresados", "finalizados", "monto_aprobado", "dias_promedio_resolucion"):
            assert set(kpis[campo]) == {"actual", "anterior"}

    def test_filtra_por_prioridad_y_categoria(self, client, crear_reclamo):
        crear_reclamo(prioridad=PrioridadReclamo.ALTA, categoria="Gas")
        crear_reclamo(prioridad=PrioridadReclamo.ALTA, categoria="Techos")
        crear_reclamo(prioridad=PrioridadReclamo.BAJA, categoria="Gas")

        cuerpo = client.get(
            "/dashboard/resumen", params={"prioridad": "ALTA", "categoria": "Gas"}
        ).json()

        assert cuerpo["kpis"]["reclamos_abiertos"] == 1

    def test_categorias_no_se_recortan_con_el_filtro(self, client, crear_reclamo):
        crear_reclamo(categoria="Techos")
        crear_reclamo(categoria="Gas")

        cuerpo = client.get("/dashboard/resumen", params={"categoria": "Gas"}).json()

        assert cuerpo["categorias"] == ["Gas", "Techos"]
