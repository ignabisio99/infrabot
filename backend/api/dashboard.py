"""Agregaciones para la pantalla de Dashboard.

Un solo endpoint que devuelve todo lo que la pantalla muestra.

Los cortes por fecha se hacen en hora local (UTC-3) y no en UTC: un reclamo cargado a
las 22 hs del 31 de agosto es de agosto para quien lo cargó, aunque en UTC ya sea
septiembre.
"""

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import HistorialEstadoReclamo
from models.presupuesto import EstadoPresupuesto, ItemPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.usuario import Usuario
from models.visita import EstadoVisita, Visita
from schemas.dashboard import (
    ConteoPorEstado,
    KpisDashboard,
    PuntoSerieMensual,
    ReclamoEstancado,
    ResumenDashboard,
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
MESES_SERIE = 6


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


def _conteo_por_estado(db: Session) -> dict[EstadoReclamo, int]:
    filas = db.query(Reclamo.estado, func.count(Reclamo.id)).group_by(Reclamo.estado).all()
    return {estado: cantidad for estado, cantidad in filas}


def _monto_aprobado_desde(db: Session, desde: datetime):
    """Suma de los presupuestos aprobados a partir de `desde`.

    La fecha que importa es la de la aprobación (el asiento del historial), no la de
    carga del presupuesto: lo que se quiere medir es lo que se comprometió este mes. El
    join no multiplica los ítems porque APROBADO es terminal, así que hay a lo sumo un
    asiento de aprobación por presupuesto.
    """
    total = (
        db.query(func.sum(ItemPresupuesto.cantidad * ItemPresupuesto.costo_unitario))
        .join(Presupuesto, Presupuesto.id == ItemPresupuesto.presupuesto_id)
        .join(
            HistorialEstadoPresupuesto,
            HistorialEstadoPresupuesto.presupuesto_id == Presupuesto.id,
        )
        .filter(
            Presupuesto.estado == EstadoPresupuesto.APROBADO,
            HistorialEstadoPresupuesto.estado_nuevo == EstadoPresupuesto.APROBADO,
            HistorialEstadoPresupuesto.fecha >= desde,
        )
        .scalar()
    )
    return total or 0


def _dias_promedio_resolucion(db: Session) -> float | None:
    """Promedio de días entre la creación del reclamo y su paso a FINALIZADO."""
    finalizacion = (
        db.query(
            HistorialEstadoReclamo.reclamo_id.label("reclamo_id"),
            func.max(HistorialEstadoReclamo.fecha).label("fecha"),
        )
        .filter(HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO)
        .group_by(HistorialEstadoReclamo.reclamo_id)
        .subquery()
    )

    segundos = (
        db.query(func.avg(func.extract("epoch", finalizacion.c.fecha - Reclamo.fecha_creacion)))
        .join(finalizacion, finalizacion.c.reclamo_id == Reclamo.id)
        .scalar()
    )

    if segundos is None:
        return None
    return round(float(segundos) / 86400, 1)


def _kpis(db: Session, ahora: datetime, conteo: dict[EstadoReclamo, int]) -> KpisDashboard:
    hace_30 = ahora - timedelta(days=30)
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    abiertos = sum(conteo.get(estado, 0) for estado in ESTADOS_ABIERTOS)

    nuevos = (
        db.query(func.count(Reclamo.id)).filter(Reclamo.fecha_creacion >= hace_30).scalar()
    )

    visitas = (
        db.query(func.count(Visita.id))
        .filter(
            Visita.estado == EstadoVisita.CONFIRMADA,
            Visita.fecha_visita >= ahora,
            Visita.fecha_visita < ahora + timedelta(days=7),
        )
        .scalar()
    )

    return KpisDashboard(
        reclamos_abiertos=abiertos,
        pendientes_revision=conteo.get(EstadoReclamo.PENDIENTE_REVISION, 0),
        en_evaluacion=conteo.get(EstadoReclamo.EN_EVALUACION, 0),
        visitas_proximos_7_dias=visitas,
        monto_aprobado_mes=_monto_aprobado_desde(db, inicio_mes),
        mes_aprobado=_clave_mes(inicio_mes),
        dias_promedio_resolucion=_dias_promedio_resolucion(db),
        nuevos_ultimos_30_dias=nuevos,
    )


def _serie_mensual(db: Session, ahora: datetime) -> list[PuntoSerieMensual]:
    desde, meses = _meses_de_la_serie(ahora, MESES_SERIE)

    mes_creacion = _mes_local(Reclamo.fecha_creacion)
    ingresados = dict(
        db.query(mes_creacion, func.count(Reclamo.id))
        .filter(Reclamo.fecha_creacion >= desde)
        .group_by(mes_creacion)
        .all()
    )

    # DISTINCT porque un reclamo reabierto podría volver a FINALIZADO dentro del mismo
    # mes, y lo que se cuenta son reclamos resueltos, no asientos del historial.
    mes_finalizacion = _mes_local(HistorialEstadoReclamo.fecha)
    finalizados = dict(
        db.query(mes_finalizacion, func.count(distinct(HistorialEstadoReclamo.reclamo_id)))
        .filter(
            HistorialEstadoReclamo.estado_nuevo == EstadoReclamo.FINALIZADO,
            HistorialEstadoReclamo.fecha >= desde,
        )
        .group_by(mes_finalizacion)
        .all()
    )

    ingresados = {_clave_mes(fecha): cantidad for fecha, cantidad in ingresados.items()}
    finalizados = {_clave_mes(fecha): cantidad for fecha, cantidad in finalizados.items()}

    return [
        PuntoSerieMensual(
            mes=clave,
            ingresados=ingresados.get(clave, 0),
            finalizados=finalizados.get(clave, 0),
        )
        for clave in meses
    ]


def _estancados(db: Session, ahora: datetime) -> tuple[int, list[ReclamoEstancado]]:
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

    estancados = (
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


@router.get("/resumen", response_model=ResumenDashboard)
def resumen(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    ahora = datetime.now(ART)
    conteo = _conteo_por_estado(db)
    total_estancados, estancados = _estancados(db, ahora)

    return ResumenDashboard(
        kpis=_kpis(db, ahora, conteo),
        # Se listan todos los estados, incluso los que están en cero: el gráfico muestra
        # el flujo completo, y una etapa vacía también es información.
        por_estado=[
            ConteoPorEstado(estado=estado, cantidad=conteo.get(estado, 0))
            for estado in EstadoReclamo
        ],
        serie_mensual=_serie_mensual(db, ahora),
        estados_abiertos=ESTADOS_ABIERTOS,
        estancados=estancados,
        estancados_total=total_estancados,
        dias_sin_movimiento_umbral=DIAS_SIN_MOVIMIENTO,
    )
