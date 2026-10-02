import { useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconDownload, IconFileText } from '@tabler/icons-react';

import { descargarReporteCsv, obtenerReporte } from '../../api/reportes';
import { notifyError } from '../../utils/notifications';

const TIPOS = [
  { label: 'Métricas', value: 'metricas' },
  { label: 'Reclamos', value: 'reclamos' },
  { label: 'Presupuestos', value: 'presupuestos' },
];

const formatoMonto = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 0,
});

function TarjetasResumen({ tipo, resumen }) {
  if (!resumen) return null;

  let tarjetas;
  if (tipo === 'metricas') {
    tarjetas = [
      { label: 'Reclamos ingresados', value: resumen.total },
      { label: 'Finalizados', value: resumen.finalizados },
      { label: 'Tasa de resolución', value: `${resumen.tasa_resolucion ?? 0}%` },
      {
        label: 'Días promedio',
        value:
          resumen.dias_promedio_resolucion === null || resumen.dias_promedio_resolucion === undefined
            ? '—'
            : resumen.dias_promedio_resolucion,
      },
      { label: 'Monto presupuestado', value: formatoMonto.format(resumen.monto_total || 0) },
      { label: 'Monto aprobado', value: formatoMonto.format(resumen.monto_aprobado || 0) },
    ];
  } else if (tipo === 'presupuestos') {
    tarjetas = [
      { label: 'Total', value: resumen.total },
      { label: 'Monto total', value: formatoMonto.format(resumen.monto_total || 0) },
      { label: 'Monto aprobado', value: formatoMonto.format(resumen.monto_aprobado || 0) },
    ];
  } else {
    tarjetas = [{ label: 'Total', value: resumen.total }];
  }

  const cols = tarjetas.length >= 3 ? 3 : tarjetas.length;
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: cols }}>
      {tarjetas.map((t) => (
        <Paper key={t.label} withBorder p="md" radius="md">
          <Text size="xs" c="dimmed" tt="uppercase">
            {t.label}
          </Text>
          <Text size="xl" fw={700}>
            {t.value}
          </Text>
        </Paper>
      ))}
    </SimpleGrid>
  );
}

function DesglosePorEstado({ resumen }) {
  const porEstado = resumen?.por_estado || {};
  const entradas = Object.entries(porEstado);
  if (entradas.length === 0) return null;
  return (
    <Group gap="xs">
      {entradas.map(([estado, cantidad]) => (
        <Badge key={estado} variant="light" tt="none">
          {estado}: {cantidad}
        </Badge>
      ))}
    </Group>
  );
}

export function ReportsPage() {
  const [tipo, setTipo] = useState('reclamos');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [reporte, setReporte] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState(false);

  const filtros = { desde: desde || undefined, hasta: hasta || undefined };

  async function generar() {
    setCargando(true);
    try {
      const data = await obtenerReporte(tipo, filtros);
      setReporte(data);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setCargando(false);
    }
  }

  async function descargar() {
    setDescargando(true);
    try {
      await descargarReporteCsv(tipo, filtros);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <Container fluid px={0}>
      <Title order={2} mb="md">
        Reportes
      </Title>

      <Paper withBorder p="md" radius="md" mb="lg">
        <Stack gap="md">
          <SegmentedControl data={TIPOS} value={tipo} onChange={setTipo} />

          <Group align="flex-end" gap="md">
            <div>
              <Text size="sm" fw={500} mb={4}>
                Desde
              </Text>
              <input
                type="date"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #ced4da' }}
              />
            </div>
            <div>
              <Text size="sm" fw={500} mb={4}>
                Hasta
              </Text>
              <input
                type="date"
                value={hasta}
                onChange={(e) => setHasta(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #ced4da' }}
              />
            </div>
            <Button leftSection={<IconFileText size={16} />} onClick={generar} loading={cargando}>
              Generar
            </Button>
            <Button
              variant="light"
              leftSection={<IconDownload size={16} />}
              onClick={descargar}
              loading={descargando}
              disabled={!reporte}
            >
              Descargar CSV
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            Dejá las fechas vacías para incluir todo el histórico.
          </Text>
        </Stack>
      </Paper>

      {cargando && <Loader />}

      {reporte && !cargando && (
        <Stack gap="md">
          <TarjetasResumen tipo={tipo} resumen={reporte.resumen} />
          <DesglosePorEstado resumen={reporte.resumen} />

          {reporte.filas.length === 0 ? (
            <Alert color="gray">No hay datos para el período seleccionado.</Alert>
          ) : (
            <Paper withBorder radius="md" style={{ overflowX: 'auto' }}>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    {reporte.columnas.map((c) => (
                      <Table.Th key={c}>{c}</Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {reporte.filas.map((fila, i) => (
                    <Table.Tr key={i}>
                      {fila.map((celda, j) => (
                        <Table.Td key={j}>{celda}</Table.Td>
                      ))}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Paper>
          )}
        </Stack>
      )}
    </Container>
  );
}
