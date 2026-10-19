import { useCallback, useEffect, useState } from 'react';
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
import { DatePickerInput } from '@mantine/dates';
import { IconDownload, IconFileTypePdf } from '@tabler/icons-react';

import { descargarReporteCsv, descargarReportePdf, obtenerReporte } from '../../api/reportes';
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
          resumen.dias_promedio_resolucion === null ||
          resumen.dias_promedio_resolucion === undefined
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
  // Mismo selector de rango que el listado de reclamos. Mantine devuelve 'YYYY-MM-DD',
  // que es lo que espera la API.
  const [rangoFechas, setRangoFechas] = useState([null, null]);
  const desde = rangoFechas[0] ?? '';
  const hasta = rangoFechas[1] ?? '';
  const [reporteGenerado, setReporte] = useState(null);
  // Sin el rango completo no se muestra nada (ni el último reporte generado).
  const reporte = desde && hasta ? reporteGenerado : null;
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState(null); // 'csv' | 'pdf' | null

  const filtros = { desde: desde || undefined, hasta: hasta || undefined };

  // Genera el reporte. Memoizado para poder usarlo como dependencia del efecto.
  const generar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await obtenerReporte(tipo, { desde, hasta });
      setReporte(data);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setCargando(false);
    }
  }, [tipo, desde, hasta]);

  // Solo genera cuando AMBAS fechas están cargadas. Así al entrar no muestra nada y,
  // una vez elegido el rango, cambiar de tipo (métricas/reclamos/presupuestos) o de
  // fechas regenera solo, sin apretar un botón. Debounce para no disparar al tipear.
  useEffect(() => {
    if (!desde || !hasta) return;
    const timer = setTimeout(generar, 300);
    return () => clearTimeout(timer);
  }, [generar, desde, hasta]);

  async function descargar(formato) {
    setDescargando(formato);
    try {
      if (formato === 'pdf') {
        await descargarReportePdf(tipo, filtros);
      } else {
        await descargarReporteCsv(tipo, filtros);
      }
    } catch (err) {
      notifyError(err.message);
    } finally {
      setDescargando(null);
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

          <Group align="flex-end" gap="md" wrap="wrap">
            <DatePickerInput
              type="range"
              allowSingleDateInRange
              label="Fecha"
              placeholder="Seleccioná un rango"
              value={rangoFechas}
              onChange={setRangoFechas}
              valueFormat="DD/MM/YYYY"
              clearable
              w={260}
            />
            <Button
              variant="light"
              leftSection={<IconDownload size={16} />}
              onClick={() => descargar('csv')}
              loading={descargando === 'csv'}
              disabled={!reporte || cargando || descargando === 'pdf'}
            >
              Descargar CSV
            </Button>
            <Button
              variant="light"
              color="red"
              leftSection={<IconFileTypePdf size={16} />}
              onClick={() => descargar('pdf')}
              loading={descargando === 'pdf'}
              disabled={!reporte || cargando || descargando === 'csv'}
            >
              Descargar PDF
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            Elegí un rango de fechas (desde y hasta) para generar el reporte. Para un solo día, tocá
            la misma fecha dos veces.
          </Text>
        </Stack>
      </Paper>

      {(!desde || !hasta) && (
        <Alert color="gray" variant="light">
          Seleccioná un rango de fechas para ver el reporte.
        </Alert>
      )}

      {cargando && !reporte && <Loader />}

      {reporte && (
        <Stack gap="md" style={{ opacity: cargando ? 0.5 : 1, transition: 'opacity 0.15s' }}>
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
