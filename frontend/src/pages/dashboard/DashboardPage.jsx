import { useEffect, useState } from 'react';
import { Alert, Container, Grid, Loader, SimpleGrid, Stack, Title } from '@mantine/core';
import {
  IconCalendarEvent,
  IconClipboardList,
  IconClockHour4,
  IconCurrencyDollar,
  IconInbox,
  IconReceipt2,
} from '@tabler/icons-react';

import { obtenerResumenDashboard } from '../../api/dashboard';
import { nombreMes } from '../../utils/meses';
import { ClaimsByStateChart } from './ClaimsByStateChart';
import { MonthlyFlowChart } from './MonthlyFlowChart';
import { StalledClaimsCard } from './StalledClaimsCard';
import { StatCard } from './StatCard';

// Sin decimales: en un indicador el peso exacto no aporta y el número queda más corto.
const formatoMonto = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 0,
});

// En verbo, para que se lea como lo que es: los que entraron en el período, no una parte
// de los abiertos que cuenta la tarjeta. "Ingresar" es el mismo término que usa el
// gráfico de ingresados vs. finalizados.
function textoIngresos(nuevos) {
  return `${nuevos} ${nuevos === 1 ? 'ingresó' : 'ingresaron'} en los últimos 30 días`;
}

export function DashboardPage() {
  const [resumen, setResumen] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    obtenerResumenDashboard()
      .then(setResumen)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const kpis = resumen?.kpis;

  return (
    <Container fluid px={0}>
      <Title order={2} mb="md">
        Dashboard
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error">
          {error}
        </Alert>
      )}

      {resumen && (
        <Stack gap="lg">
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            <StatCard
              label="Reclamos abiertos"
              value={kpis.reclamos_abiertos}
              hint={textoIngresos(kpis.nuevos_ultimos_30_dias)}
              icon={IconClipboardList}
              to={`/reclamos?estado=${resumen.estados_abiertos.join(',')}`}
            />
            <StatCard
              label="Pendientes de revisión"
              value={kpis.pendientes_revision}
              hint="Esperan la validación inicial"
              icon={IconInbox}
              to="/reclamos?estado=PENDIENTE_REVISION"
            />
            <StatCard
              label="Presupuestos a evaluar"
              value={kpis.en_evaluacion}
              hint="Reclamos con ofertas para comparar"
              icon={IconReceipt2}
              to="/reclamos?estado=EN_EVALUACION"
            />
            <StatCard
              label="Visitas próximos 7 días"
              value={kpis.visitas_proximos_7_dias}
              hint="Con fecha confirmada"
              icon={IconCalendarEvent}
            />
            <StatCard
              label={`Aprobado en ${nombreMes(kpis.mes_aprobado)}`}
              value={formatoMonto.format(Number(kpis.monto_aprobado_mes))}
              hint="Suma de los presupuestos aprobados este mes"
              icon={IconCurrencyDollar}
            />
            <StatCard
              label="Resolución promedio"
              value={
                kpis.dias_promedio_resolucion === null
                  ? '—'
                  : `${kpis.dias_promedio_resolucion.toLocaleString('es-AR')} días`
              }
              hint={
                kpis.dias_promedio_resolucion === null
                  ? 'Todavía no hay reclamos finalizados'
                  : 'Desde el ingreso hasta la finalización'
              }
              icon={IconClockHour4}
            />
          </SimpleGrid>

          <Grid>
            <Grid.Col span={{ base: 12, lg: 5 }}>
              <ClaimsByStateChart datos={resumen.por_estado} />
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
