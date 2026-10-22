import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import {
  Alert,
  Container,
  Grid,
  Group,
  Loader,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Title,
} from '@mantine/core';
import {
  IconCalendarEvent,
  IconCircleCheck,
  IconCirclePlus,
  IconClipboardList,
  IconClockHour4,
  IconCurrencyDollar,
  IconInbox,
  IconReceipt2,
} from '@tabler/icons-react';

import { obtenerResumenDashboard } from '../../api/dashboard';
import { ClaimsByStateChart } from './ClaimsByStateChart';
import { DashboardSkeleton } from './DashboardSkeleton';
import { MonthlyFlowChart } from './MonthlyFlowChart';
import { StalledClaimsCard } from './StalledClaimsCard';
import { StatCard } from './StatCard';

// Sin decimales: en un indicador el peso exacto no aporta y el número queda más corto.
const formatoMonto = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 0,
});

// Los mismos valores que acepta el backend (PeriodoDias).
const PERIODOS = [
  { value: '30', label: '30 días' },
  { value: '90', label: '90 días' },
  { value: '365', label: '12 meses' },
];
const PERIODO_POR_DEFECTO = '30';

const PRIORIDADES = [
  { value: 'ALTA', label: 'Alta' },
  { value: 'MEDIA', label: 'Media' },
  { value: 'BAJA', label: 'Baja' },
];

// Los filtros viven en la URL: al volver desde un listado al que se entró por una
// tarjeta, el dashboard queda como estaba.
function filtrosDeParams(searchParams) {
  const periodo = searchParams.get('periodo');
  const prioridad = searchParams.get('prioridad');
  return {
    periodo: PERIODOS.some((p) => p.value === periodo) ? periodo : PERIODO_POR_DEFECTO,
    // Inválida se ignora: el backend la rechazaría con 422 y el Select no tendría qué limpiar.
    prioridad: PRIORIDADES.some((p) => p.value === prioridad) ? prioridad : '',
    categoria: searchParams.get('categoria') ?? '',
  };
}

function textoDias(dias) {
  return dias === null ? '—' : `${dias.toLocaleString('es-AR')} días`;
}

export function DashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { periodo, prioridad, categoria } = filtrosDeParams(searchParams);
  const clave = `${periodo}|${prioridad}|${categoria}`;

  // Cada resultado guarda para qué filtros se pidió: así "actualizando" se deduce de
  // comparar claves y no hace falta prender un flag dentro del effect.
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const pedida = `${periodo}|${prioridad}|${categoria}`;
    // Si se cambia de filtro antes de que vuelva la respuesta anterior, esa respuesta ya
    // no corresponde a lo que está elegido y se descarta.
    let vigente = true;

    obtenerResumenDashboard({ periodo, prioridad, categoria })
      .then((resumen) => vigente && setResultado({ clave: pedida, resumen }))
      .catch((err) => vigente && setError({ clave: pedida, mensaje: err.message }));

    return () => {
      vigente = false;
    };
  }, [periodo, prioridad, categoria]);

  const fallo = error?.clave === clave ? error.mensaje : null;
  const resumen = resultado?.resumen;
  const desactualizado = Boolean(resultado) && resultado.clave !== clave;
  const actualizando = desactualizado && !fallo;

  const cambiarFiltro = (nombre, valor) => {
    const siguientes = new URLSearchParams(searchParams);
    if (!valor || (nombre === 'periodo' && valor === PERIODO_POR_DEFECTO)) {
      siguientes.delete(nombre);
    } else {
      siguientes.set(nombre, valor);
    }
    setSearchParams(siguientes, { replace: true });
  };

  const linkReclamos = (estados) => {
    const params = new URLSearchParams({ estado: estados.join(',') });
    if (prioridad) params.set('prioridad', prioridad);
    if (categoria) params.set('categoria', categoria);
    return `/reclamos?${params}`;
  };

  const categorias = resumen?.categorias ?? [];

  // Del período que vino en la respuesta y no del elegido: mientras llega la nueva, los
  // números que se ven siguen siendo los del período anterior y el texto tiene que coincidir.
  const etiquetaPeriodo = PERIODOS.find((p) => p.value === String(resumen?.periodo_dias))?.label;
  const contra = `${etiquetaPeriodo} anteriores`;
  const kpis = resumen?.kpis;
  const serie = (campo) => resumen.serie_mensual.map((punto) => Number(punto[campo]));
  const etiquetaSerie = resumen && `Por mes, últimos ${resumen.serie_mensual.length} meses`;

  return (
    <Container fluid px={0}>
      <Group justify="space-between" align="flex-end" mb="md" gap="sm">
        <Group gap="xs">
          <Title order={2}>Dashboard</Title>
          {actualizando && <Loader size="xs" aria-label="Actualizando" />}
        </Group>

        <Group gap="sm" wrap="wrap">
          <SegmentedControl
            aria-label="Período"
            data={PERIODOS}
            value={periodo}
            onChange={(valor) => cambiarFiltro('periodo', valor)}
          />
          <Select
            aria-label="Prioridad"
            placeholder="Todas las prioridades"
            data={PRIORIDADES}
            value={prioridad || null}
            onChange={(valor) => cambiarFiltro('prioridad', valor)}
            clearable
            w={190}
          />
          <Select
            aria-label="Categoría"
            placeholder="Todas las categorías"
            data={
              categoria && !categorias.includes(categoria) ? [...categorias, categoria] : categorias
            }
            value={categoria || null}
            onChange={(valor) => cambiarFiltro('categoria', valor)}
            clearable
            searchable
            nothingFoundMessage="Sin coincidencias"
            w={200}
          />
        </Group>
      </Group>

      {fallo && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {fallo}
        </Alert>
      )}

      {!resumen && !fallo && <DashboardSkeleton />}

      {resumen && (
        <Stack
          gap="lg"
          style={{ opacity: desactualizado ? 0.55 : 1, transition: 'opacity 150ms ease' }}
        >
          <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
            <StatCard
              label="Reclamos abiertos"
              value={kpis.reclamos_abiertos}
              hint="Sin finalizar, rechazar ni cancelar"
              icon={IconClipboardList}
              to={linkReclamos(resumen.estados_abiertos)}
            />
            <StatCard
              label="Pendientes de revisión"
              value={kpis.pendientes_revision}
              hint="Esperan la validación inicial"
              icon={IconInbox}
              to={linkReclamos(['PENDIENTE_REVISION'])}
            />
            <StatCard
              label="Presupuestos a evaluar"
              value={kpis.en_evaluacion}
              hint="Reclamos con ofertas para comparar"
              icon={IconReceipt2}
              to={linkReclamos(['EN_EVALUACION'])}
            />
            <StatCard
              label="Visitas próximos 7 días"
              value={kpis.visitas_proximos_7_dias}
              hint={
                prioridad || categoria
                  ? 'Con fecha confirmada. El calendario muestra todas'
                  : 'Con fecha confirmada'
              }
              icon={IconCalendarEvent}
              to="/calendario"
            />
            <StatCard
              label="Ingresados"
              value={kpis.ingresados.actual}
              hint={`En los últimos ${etiquetaPeriodo}`}
              icon={IconCirclePlus}
              comparacion={{ ...kpis.ingresados, contra }}
              serie={serie('ingresados')}
              etiquetaSerie={etiquetaSerie}
            />
            <StatCard
              label="Finalizados"
              value={kpis.finalizados.actual}
              hint={`En los últimos ${etiquetaPeriodo}`}
              icon={IconCircleCheck}
              comparacion={{ ...kpis.finalizados, contra, mejorSi: 'sube' }}
              serie={serie('finalizados')}
              etiquetaSerie={etiquetaSerie}
            />
            <StatCard
              label="Monto aprobado"
              value={formatoMonto.format(Number(kpis.monto_aprobado.actual))}
              hint={`Presupuestos aprobados en los últimos ${etiquetaPeriodo}`}
              icon={IconCurrencyDollar}
              comparacion={{ ...kpis.monto_aprobado, contra }}
              serie={serie('monto_aprobado')}
              etiquetaSerie={etiquetaSerie}
            />
            <StatCard
              label="Resolución promedio"
              value={textoDias(kpis.dias_promedio_resolucion.actual)}
              hint={
                kpis.dias_promedio_resolucion.actual === null
                  ? 'Ningún reclamo finalizado en el período'
                  : 'Desde el ingreso hasta la finalización'
              }
              icon={IconClockHour4}
              comparacion={{ ...kpis.dias_promedio_resolucion, contra, mejorSi: 'baja' }}
            />
          </SimpleGrid>

          <Grid>
            <Grid.Col span={{ base: 12, lg: 5 }}>
              <ClaimsByStateChart datos={resumen.por_estado} linkReclamos={linkReclamos} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 7 }}>
              <MonthlyFlowChart datos={resumen.serie_mensual} />
            </Grid.Col>
          </Grid>

          <StalledClaimsCard
            reclamos={resumen.estancados}
            total={resumen.estancados_total}
            umbral={resumen.dias_sin_movimiento_umbral}
          />
        </Stack>
      )}
    </Container>
  );
}
