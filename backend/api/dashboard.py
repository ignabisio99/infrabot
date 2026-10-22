"""Agregaciones para la pantalla de Dashboard.

Un solo endpoint que devuelve todo lo que la pantalla muestra.

Los cortes por fecha se hacen en hora local (UTC-3) y no en UTC: un reclamo cargado a
las 22 hs del 31 de agosto es de agosto para quien lo cargó, aunque en UTC ya sea
septiembre.
"""

import enum
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, distinct, func
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import HistorialEstadoReclamo
from models.presupuesto import EstadoPresupuesto, ItemPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, PrioridadReclamo, Reclamo
from models.usuario import Usuario
from models.visita import EstadoVisita, Visita
from schemas.dashboard import (
    Comparacion,
    ConteoPorEstado,
    EtapaFlujo,
    KpisDashboard,
    PuntoSerieMensual,
    ReclamoEstancado,
    ResumenDashboard,
    TiempoEtapa,
)
from services.estados_reclamo import ESTADOS_FINALES

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# El huso local, uno solo para los dos lados: Python lo usa para acotar los rangos y
# Postgres para truncar al mes (`_mes_local`).
TZ_LOCAL = "America/Argentina/Buenos_Aires"
ART = ZoneInfo(TZ_LOCAL)

# Los estados que cuentan como abiertos, en el orden del enum. DESIERTO está entre ellos:
# la máquina de estados lo deja volver a PENDIENTE_PRESUPUESTO, así que es un reclamo que
# sigue esperando una acción.
ESTADOS_ABIERTOS = [estado for estado in EstadoReclamo if estado not in ESTADOS_FINALES]

# Días sin cambio de estado a partir de los cuales un reclamo abierto se considera
# estancado.
DIAS_SIN_MOVIMIENTO = 7
MAX_ESTANCADOS = 8

# Qué estados forman cada etapa. DESIERTO va en presupuesto porque de ahí se vuelve a
# pedir cotizaciones: un reclamo que pasa por desierto sigue sumando tiempo de presupuesto.
ESTADOS_POR_ETAPA = {
    EtapaFlujo.REVISION: [EstadoReclamo.PENDIENTE_REVISION],
    EtapaFlujo.PRESUPUESTO: [
        EstadoReclamo.PENDIENTE_PRESUPUESTO,
        EstadoReclamo.EN_EVALUACION,
        EstadoReclamo.DESIERTO,
    ],
    EtapaFlujo.EJECUCION: [
        EstadoReclamo.APROBADO,
        EstadoReclamo.PENDIENTE_COORDINACION,
        EstadoReclamo.VISITA_COORDINADA,
        EstadoReclamo.EN_EJECUCION,
        EstadoReclamo.PENDIENTE_INTERVENCION,
    ],
}


class PeriodoDias(enum.IntEnum):
    # IntEnum y no Literal: el query string llega como texto y Literal[30, ...] no
    # convierte "30" a 30, así que rechazaría cualquier período pedido por URL.
    MES = 30
    TRIMESTRE = 90
    ANIO = 365


def _cantidad_de_meses(periodo: PeriodoDias) -> int:
    """Con el período de un año la serie muestra el año entero; con los cortos, medio año:
    un gráfico de uno o tres puntos no muestra ninguna tendencia."""
    return 12 if periodo == PeriodoDias.ANIO else 6


@dataclass(frozen=True)
class Filtros:
    """Recorte por prioridad y categoría que se aplica a todas las agregaciones.

    Cada consulta que lo usa tiene que tener `Reclamo` en el FROM (directo o por join).
    """

    prioridad: PrioridadReclamo | None = None
    categoria: str | None = None

    def aplicar(self, query):
        if self.prioridad is not None:
            query = query.filter(Reclamo.prioridad == self.prioridad)
        if self.categoria is not None:
            query = query.filter(Reclamo.categoria == self.categoria)
        return query


SIN_FILTROS = Filtros()


def _entre(columna, desde: datetime, hasta: datetime | None):
    """`desde <= columna < hasta`. Sin `hasta` no hay tope: así el período en curso
    incluye lo cargado en el mismo instante del cálculo."""
    if hasta is None:
        return columna >= desde
    return and_(columna >= desde, columna < hasta)


def _meses_de_la_serie(hasta: datetime, cantidad: int) -> tuple[datetime, list[str]]:
    """Desde cuándo arranca la serie y las claves "YYYY-MM" de sus meses, del más viejo
    al más nuevo.

    Las claves salen de acá y no de lo que devuelva la base, así los meses sin movimiento
    aparecen en cero en vez de desaparecer del gráfico.

    La cuenta va sobre el mes como número absoluto (año * 12 + mes) para no tener que
    manejar a mano el salto de diciembre a enero.
    """
    ultimo = hasta.year * 12 + hasta.month - 1
    primero = ultimo - cantidad + 1
    claves = [f"{mes // 12:04d}-{mes % 12 + 1:02d}" for mes in range(primero, ultimo + 1)]
    return datetime(primero // 12, primero % 12 + 1, 1, tzinfo=ART), claves


def _mes_local(columna):
    """Expresión SQL que trunca una fecha al mes, en hora local.

    Va etiquetada porque el GROUP BY tiene que referirse al alias: repetir la expresión
    manda los literales como dos parámetros distintos y Postgres no los reconoce como la
    misma columna.
    """
    return func.date_trunc("month", func.timezone(TZ_LOCAL, columna)).label("mes")


def _clave_mes(valor: datetime) -> str:
    return f"{valor.year:04d}-{valor.month:02d}"


def _conteo_por_estado(db: Session, filtros: Filtros = SIN_FILTROS) -> dict[EstadoReclamo, int]:
    query = db.query(Reclamo.estado, func.count(Reclamo.id))
    filas = filtros.aplicar(query).group_by(Reclamo.estado).all()
    return {estado: cantidad for estado, cantidad in filas}


def _ingresados(
    db: Session, desde: datetime, hasta: datetime | None = None, filtros: Filtros = SIN_FILTROS
) -> int:
    query = db.query(func.count(Reclamo.id)).filter(_entre(Reclamo.fecha_creacion, desde, hasta))
    return filtros.aplicar(query).scalar()


def _finalizados(
    db: Session, desde: datetime, hasta: datetime | None = None, filtros: Filtros = SIN_FILTROS
) -> int:
    """Reclamos con un asiento de FINALIZADO en el rango.

    DISTINCT por lo mismo que en la serie mensual: lo que se cuenta son reclamos
    resueltos, no asientos del historial.
    """
    query = (
        db.query(func.count(distinct(HistorialEstadoReclamo.reclamo_id)))
        .join(Reclamo, Reclamo.id == HistorialEstadoReclamo.reclamo_id)
        .filter(
            HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO,
            _entre(HistorialEstadoReclamo.fecha, desde, hasta),
        )
    )
    return filtros.aplicar(query).scalar()


def _query_monto_aprobado(db: Session, *columnas):
    """Suma de los presupuestos aprobados, por fecha de aprobación.

    La fecha que importa es la de la aprobación (el asiento del historial), no la de
    carga del presupuesto: lo que se quiere medir es lo que se comprometió en el período.
    El join no multiplica los ítems porque APROBADO es terminal, así que hay a lo sumo un
    asiento de aprobación por presupuesto.
    """
    return (
        db.query(*columnas, func.sum(ItemPresupuesto.cantidad * ItemPresupuesto.costo_unitario))
        .select_from(ItemPresupuesto)
        .join(Presupuesto, Presupuesto.id == ItemPresupuesto.presupuesto_id)
        .join(Reclamo, Reclamo.id == Presupuesto.reclamo_id)
        .join(
            HistorialEstadoPresupuesto,
            HistorialEstadoPresupuesto.presupuesto_id == Presupuesto.id,
        )
        .filter(
            Presupuesto.estado == EstadoPresupuesto.APROBADO,
            HistorialEstadoPresupuesto.estado_nuevo == EstadoPresupuesto.APROBADO,
        )
    )


def _monto_aprobado(
    db: Session, desde: datetime, hasta: datetime | None = None, filtros: Filtros = SIN_FILTROS
):
    query = _query_monto_aprobado(db).filter(
        _entre(HistorialEstadoPresupuesto.fecha, desde, hasta)
    )
    return filtros.aplicar(query).scalar() or 0


def _dias_promedio_resolucion(
    db: Session, desde: datetime, hasta: datetime | None = None, filtros: Filtros = SIN_FILTROS
) -> float | None:
    """Promedio de días entre la creación y el paso a FINALIZADO, de los reclamos que se
    finalizaron en el rango.

    El rango se aplica antes del max: si no, un reclamo reabierto y vuelto a finalizar
    desaparece del período de su primera finalización, aunque `_finalizados` lo cuente ahí.
    """
    finalizacion = (
        db.query(
            HistorialEstadoReclamo.reclamo_id.label("reclamo_id"),
            func.max(HistorialEstadoReclamo.fecha).label("fecha"),
        )
        .filter(
            HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO,
            _entre(HistorialEstadoReclamo.fecha, desde, hasta),
        )
        .group_by(HistorialEstadoReclamo.reclamo_id)
        .subquery()
    )

    query = db.query(
        func.avg(func.extract("epoch", finalizacion.c.fecha - Reclamo.fecha_creacion))
    ).join(finalizacion, finalizacion.c.reclamo_id == Reclamo.id)
    segundos = filtros.aplicar(query).scalar()

    if segundos is None:
        return None
    return round(float(segundos) / 86400, 1)


def _comparacion(calcular, ahora: datetime, periodo_dias: int) -> Comparacion:
    """`calcular(desde, hasta)` para el período que termina ahora y para el anterior."""
    largo = timedelta(days=periodo_dias)
    desde = ahora - largo
    return Comparacion(actual=calcular(desde, None), anterior=calcular(desde - largo, desde))


def _kpis(
    db: Session,
    ahora: datetime,
    conteo: dict[EstadoReclamo, int],
    periodo_dias: int = 30,
    filtros: Filtros = SIN_FILTROS,
) -> KpisDashboard:
    abiertos = sum(conteo.get(estado, 0) for estado in ESTADOS_ABIERTOS)

    visitas = (
        db.query(func.count(Visita.id))
        .join(Reclamo, Reclamo.id == Visita.reclamo_id)
        .filter(
            Visita.estado == EstadoVisita.CONFIRMADA,
            Visita.fecha_visita >= ahora,
            Visita.fecha_visita < ahora + timedelta(days=7),
        )
    )

    def comparar(funcion):
        return _comparacion(
            lambda desde, hasta: funcion(db, desde, hasta, filtros), ahora, periodo_dias
        )

    return KpisDashboard(
        reclamos_abiertos=abiertos,
        pendientes_revision=conteo.get(EstadoReclamo.PENDIENTE_REVISION, 0),
        en_evaluacion=conteo.get(EstadoReclamo.EN_EVALUACION, 0),
        visitas_proximos_7_dias=filtros.aplicar(visitas).scalar(),
        ingresados=comparar(_ingresados),
        finalizados=comparar(_finalizados),
        monto_aprobado=comparar(_monto_aprobado),
        dias_promedio_resolucion=comparar(_dias_promedio_resolucion),
    )


def _serie_mensual(
    db: Session, ahora: datetime, meses: int = 6, filtros: Filtros = SIN_FILTROS
) -> list[PuntoSerieMensual]:
    desde, claves = _meses_de_la_serie(ahora, meses)

    mes_creacion = _mes_local(Reclamo.fecha_creacion)
    ingresados = (
        db.query(mes_creacion, func.count(Reclamo.id)).filter(Reclamo.fecha_creacion >= desde)
    )

    # DISTINCT porque un reclamo reabierto podría volver a FINALIZADO dentro del mismo
    # mes, y lo que se cuenta son reclamos resueltos, no asientos del historial.
    mes_finalizacion = _mes_local(HistorialEstadoReclamo.fecha)
    finalizados = (
        db.query(mes_finalizacion, func.count(distinct(HistorialEstadoReclamo.reclamo_id)))
        .join(Reclamo, Reclamo.id == HistorialEstadoReclamo.reclamo_id)
        .filter(
            HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO,
            HistorialEstadoReclamo.fecha >= desde,
        )
    )

    mes_aprobacion = _mes_local(HistorialEstadoPresupuesto.fecha)
    aprobado = _query_monto_aprobado(db, mes_aprobacion).filter(
        HistorialEstadoPresupuesto.fecha >= desde
    )

    def por_mes(query, mes):
        filas = filtros.aplicar(query).group_by(mes).all()
        return {_clave_mes(fecha): valor for fecha, valor in filas}

    ingresados = por_mes(ingresados, mes_creacion)
    finalizados = por_mes(finalizados, mes_finalizacion)
    aprobado = por_mes(aprobado, mes_aprobacion)

    return [
        PuntoSerieMensual(
            mes=clave,
            ingresados=ingresados.get(clave, 0),
            finalizados=finalizados.get(clave, 0),
            monto_aprobado=aprobado.get(clave, 0),
        )
        for clave in claves
    ]


def _estancados(
    db: Session, ahora: datetime, filtros: Filtros = SIN_FILTROS
) -> tuple[int, list[ReclamoEstancado]]:
    """Los `MAX_ESTANCADOS` más antiguos, y cuántos hay en total.

    El total va aparte del recorte para que la pantalla pueda decir que está mostrando
    una parte: si no, ocho de cuarenta se leen como si fueran todos.
    """
    limite = ahora - timedelta(days=DIAS_SIN_MOVIMIENTO)

    ultimo_movimiento = (
        db.query(
            HistorialEstadoReclamo.reclamo_id.label("reclamo_id"),
            func.max(HistorialEstadoReclamo.fecha).label("fecha"),
        )
        .group_by(HistorialEstadoReclamo.reclamo_id)
        .subquery()
    )

    # Coalesce por los reclamos anteriores al historial, que no tienen ningún asiento:
    # para esos el último movimiento es su propia creación.
    fecha_movimiento = func.coalesce(ultimo_movimiento.c.fecha, Reclamo.fecha_creacion)

    estancados = filtros.aplicar(
        db.query(Reclamo, fecha_movimiento.label("fecha"))
        .outerjoin(ultimo_movimiento, ultimo_movimiento.c.reclamo_id == Reclamo.id)
        .filter(Reclamo.estado.notin_(list(ESTADOS_FINALES)), fecha_movimiento < limite)
    )

    filas = estancados.order_by(fecha_movimiento.asc()).limit(MAX_ESTANCADOS).all()

    return estancados.count(), [
        ReclamoEstancado(
            id=reclamo.id,
            nombre_escuela=reclamo.nombre_escuela,
            estado=reclamo.estado,
            prioridad=reclamo.prioridad,
            # Hacia arriba: con `.days` un reclamo de 7 días y medio se muestra como 7,
            # justo debajo del texto que dice que están todos por encima de 7.
            dias_sin_movimiento=math.ceil((ahora - fecha).total_seconds() / 86400),
        )
        for reclamo, fecha in filas
    ]


def _tiempo_por_etapa(
    db: Session, desde: datetime, hasta: datetime | None = None, filtros: Filtros = SIN_FILTROS
) -> list[TiempoEtapa]:
    """Días promedio que un reclamo pasa en cada etapa.

    Cada asiento del historial cierra una estadía en `estado_anterior`, que empezó en el
    asiento previo del mismo reclamo (o en su creación, para los anteriores al
    historial). Por reclamo se suman todas sus estadías de la etapa, también las de
    idas y vueltas como DESIERTO -> PENDIENTE_PRESUPUESTO, y después se promedia entre
    reclamos.

    Sólo cuentan las estadías que terminaron en el rango: la de un reclamo que todavía
    está en la etapa no tiene duración final, y la muestra la tabla de estancados.
    """
    inicio = func.coalesce(
        func.lag(HistorialEstadoReclamo.fecha).over(
            partition_by=HistorialEstadoReclamo.reclamo_id,
            order_by=HistorialEstadoReclamo.fecha,
        ),
        Reclamo.fecha_creacion,
    )
    etapa = case(
        *[
            (HistorialEstadoReclamo.estado_anterior.in_(estados), clave.value)
            for clave, estados in ESTADOS_POR_ETAPA.items()
        ],
        else_=None,
    )

    # El lag se calcula antes de recortar por fecha: si no, la primera estadía dentro del
    # rango tomaría como inicio la creación del reclamo en vez del asiento anterior.
    estadias = filtros.aplicar(
        db.query(
            HistorialEstadoReclamo.reclamo_id.label("reclamo_id"),
            etapa.label("etapa"),
            HistorialEstadoReclamo.fecha.label("fin"),
            func.extract("epoch", HistorialEstadoReclamo.fecha - inicio).label("segundos"),
        ).join(Reclamo, Reclamo.id == HistorialEstadoReclamo.reclamo_id)
    ).subquery()

    por_reclamo = (
        db.query(
            estadias.c.etapa.label("etapa"),
            func.sum(estadias.c.segundos).label("segundos"),
        )
        .filter(estadias.c.etapa.isnot(None), _entre(estadias.c.fin, desde, hasta))
        .group_by(estadias.c.reclamo_id, estadias.c.etapa)
        .subquery()
    )

    filas = (
        db.query(
            por_reclamo.c.etapa,
            func.avg(por_reclamo.c.segundos),
            func.count(),
        )
        .group_by(por_reclamo.c.etapa)
        .all()
    )
    por_etapa = {etapa: (segundos, cantidad) for etapa, segundos, cantidad in filas}

    return [
        TiempoEtapa(
            etapa=etapa,
            dias_promedio=(
                round(float(por_etapa[etapa.value][0]) / 86400, 1)
                if etapa.value in por_etapa
                else None
            ),
            reclamos=por_etapa.get(etapa.value, (None, 0))[1],
        )
        for etapa in EtapaFlujo
    ]


def _categorias(db: Session) -> list[str]:
    filas = db.query(distinct(Reclamo.categoria)).order_by(Reclamo.categoria).all()
    return [categoria for (categoria,) in filas]


@router.get("/resumen", response_model=ResumenDashboard)
def resumen(
    periodo: PeriodoDias = PeriodoDias.MES,
    prioridad: PrioridadReclamo | None = None,
    categoria: str | None = None,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    ahora = datetime.now(ART)
    filtros = Filtros(prioridad=prioridad, categoria=categoria or None)
    conteo = _conteo_por_estado(db, filtros)
    total_estancados, estancados = _estancados(db, ahora, filtros)

    return ResumenDashboard(
        periodo_dias=periodo,
        kpis=_kpis(db, ahora, conteo, periodo, filtros),
        # Se listan todos los estados, incluso los que están en cero: el gráfico muestra
        # el flujo completo, y una etapa vacía también es información.
        por_estado=[
            ConteoPorEstado(estado=estado, cantidad=conteo.get(estado, 0))
            for estado in EstadoReclamo
        ],
        serie_mensual=_serie_mensual(db, ahora, _cantidad_de_meses(periodo), filtros),
        tiempo_por_etapa=_tiempo_por_etapa(
            db, ahora - timedelta(days=periodo), filtros=filtros
        ),
        estados_abiertos=ESTADOS_ABIERTOS,
        estancados=estancados,
        estancados_total=total_estancados,
        dias_sin_movimiento_umbral=DIAS_SIN_MOVIMIENTO,
        categorias=_categorias(db),
    )
