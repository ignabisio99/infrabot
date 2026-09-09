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
    _clave_mes,
    _conteo_por_estado,
    _dias_promedio_resolucion,
    _estancados,
    _kpis,
    _meses_de_la_serie,
    _monto_aprobado_desde,
    _serie_mensual,
)
from conftest import UTC
from models.reclamo import EstadoReclamo
from models.visita import EstadoVisita

AHORA = datetime(2026, 9, 15, 12, 0, tzinfo=ART)
INICIO_MES = datetime(2026, 9, 1, tzinfo=ART)


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

        assert _monto_aprobado_desde(db, INICIO_MES) == Decimal("3500.00")

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

        assert _monto_aprobado_desde(db, INICIO_MES) == Decimal("500.00")

    def test_ignora_lo_aprobado_antes_del_corte(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo,
            items=[(1, 9999)],
            fecha_aprobacion=INICIO_MES - timedelta(minutes=1),
        )

        assert _monto_aprobado_desde(db, INICIO_MES) == 0

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

        assert _monto_aprobado_desde(db, INICIO_MES) == Decimal("4000.00")

    def test_sin_aprobaciones_devuelve_cero(self, db):
        assert _monto_aprobado_desde(db, INICIO_MES) == 0


# --- Días promedio de resolución -------------------------------------------------------


class TestDiasPromedioResolucion:
    def test_sin_reclamos_finalizados_devuelve_none(self, db, crear_reclamo):
        crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)

        assert _dias_promedio_resolucion(db) is None

    def test_mide_desde_la_creacion_hasta_el_asiento_de_finalizado(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO,
            fecha_creacion=AHORA - timedelta(days=10),
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=2))

        assert _dias_promedio_resolucion(db) == 8.0

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
        assert _dias_promedio_resolucion(db) == 10.0

    def test_toma_la_ultima_finalizacion_de_un_reclamo_reabierto(
        self, db, crear_reclamo, crear_historial
    ):
        reclamo = crear_reclamo(
            estado=EstadoReclamo.FINALIZADO, fecha_creacion=AHORA - timedelta(days=30)
        )
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=25))
        crear_historial(reclamo, EstadoReclamo.FINALIZADO, AHORA - timedelta(days=10))

        assert _dias_promedio_resolucion(db) == 20.0


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

    def test_nuevos_cuenta_solo_los_ultimos_30_dias(self, db, crear_reclamo):
        for dias in (0, 1, 29):
            crear_reclamo(fecha_creacion=AHORA - timedelta(days=dias))
        for dias in (31, 90):
            crear_reclamo(fecha_creacion=AHORA - timedelta(days=dias))

        assert self._kpis_de(db).nuevos_ultimos_30_dias == 3

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

    def test_mes_aprobado_es_el_mes_del_monto(
        self, db, crear_reclamo, crear_presupuesto_aprobado
    ):
        reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
        crear_presupuesto_aprobado(
            reclamo, items=[(1, 700)], fecha_aprobacion=AHORA - timedelta(days=1)
        )

        kpis = self._kpis_de(db)

        assert kpis.mes_aprobado == "2026-09"
        assert kpis.monto_aprobado_mes == Decimal("700.00")

    def test_base_vacia_no_rompe(self, db):
        kpis = self._kpis_de(db)

        assert kpis.reclamos_abiertos == 0
        assert kpis.monto_aprobado_mes == 0
        assert kpis.dias_promedio_resolucion is None


# --- Endpoint --------------------------------------------------------------------------


class TestEndpointResumen:
    def test_devuelve_el_resumen_completo(self, client, crear_reclamo):
        crear_reclamo(estado=EstadoReclamo.EN_EVALUACION)

        respuesta = client.get("/dashboard/resumen")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert set(cuerpo) == {
            "kpis",
            "por_estado",
            "serie_mensual",
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
