import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconGavel, IconListDetails, IconShieldCheck } from '@tabler/icons-react';

import { listarPresupuestos } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { fechaEnRango, idCoincideConBusqueda } from '../../utils/filtros';
import { formatoMoneda } from '../../utils/formatters';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { StatusFilterPopover } from '../claims/StatusFilterPopover';
import { BudgetAuditModal } from './BudgetAuditModal';
import { BudgetItemsModal } from './BudgetItemsModal';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { DecideBudgetModal } from './DecideBudgetModal';
import { ESTADOS, etiquetaPorEstado } from './estados';

// Ofertas anteriores del mismo contratista en el mismo reclamo, por id de presupuesto.
// Tras un rechazo puede mandar otra, y sin esto las dos filas parecen no tener relación.
function ofertasAnterioresPorId(presupuestos) {
  const porContratistaYReclamo = new Map();
  for (const p of [...presupuestos].sort((a, b) => a.id - b.id)) {
    const clave = `${p.reclamo.id}-${p.contratista.id}`;
    porContratistaYReclamo.set(clave, [...(porContratistaYReclamo.get(clave) ?? []), p]);
  }
  const resultado = new Map();
  for (const ofertas of porContratistaYReclamo.values()) {
    ofertas.forEach((p, i) => resultado.set(p.id, ofertas.slice(0, i)));
  }
  return resultado;
}

export function BudgetsListPage() {
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [presupuestoSeleccionado, setPresupuestoSeleccionado] = useState(null);
  const [presupuestoAAuditar, setPresupuestoAAuditar] = useState(null);
  const [presupuestoADecidir, setPresupuestoADecidir] = useState(null);
  const ofertasAnteriores = useMemo(() => ofertasAnterioresPorId(presupuestos), [presupuestos]);

  const [busquedaReclamo, setBusquedaReclamo] = useState('');
  const [estadosFiltro, setEstadosFiltro] = useState([]);
  const [rangoFechas, setRangoFechas] = useState([null, null]);

  const presupuestosFiltrados = useMemo(
    () =>
      presupuestos.filter(
        (presupuesto) =>
          idCoincideConBusqueda(presupuesto.reclamo.id, busquedaReclamo) &&
          // Sin estados elegidos no se filtra: ninguno tildado es "todos".
          (estadosFiltro.length === 0 || estadosFiltro.includes(presupuesto.estado)) &&
          fechaEnRango(presupuesto.fecha, rangoFechas),
      ),
    [presupuestos, busquedaReclamo, estadosFiltro, rangoFechas],
  );

  const hayFiltrosActivos =
    busquedaReclamo !== '' ||
    estadosFiltro.length > 0 ||
    rangoFechas[0] !== null ||
    rangoFechas[1] !== null;

  const limpiarFiltros = () => {
    setBusquedaReclamo('');
    setEstadosFiltro([]);
    setRangoFechas([null, null]);
  };

  const cargar = useCallback(
    () =>
      listarPresupuestos()
        .then(setPresupuestos)
        .catch((err) => setError(err.message))
        .finally(() => setCargando(false)),
    [],
  );

  useEffect(() => {
    cargar();
  }, [cargar]);

  const esMobile = useEsMobile();

  const badgesOferta = (presupuesto, anteriores) => (
    <>
      {presupuesto.version > 1 && (
        <Badge ml={6} size="xs" color="gray" variant="outline" tt="none">
          Versión {presupuesto.version}
        </Badge>
      )}
      {anteriores.length > 0 && (
        <Tooltip
          multiline
          w={260}
          label={anteriores
            .map(
              (p) =>
                `Oferta anterior: ${formatoMoneda.format(Number(p.monto))}, ${(
                  etiquetaPorEstado[p.estado] ?? p.estado
                ).toLowerCase()}`,
            )
            .join('\n')}
        >
          <Badge ml={6} size="xs" color="violet" variant="light" tt="none">
            {anteriores.length + 1}.ª oferta
          </Badge>
        </Tooltip>
      )}
    </>
  );

  const botonesPresupuesto = (presupuesto) => (
    <>
      {presupuesto.estado !== 'APROBADO' && (
        <Button
          size="xs"
          variant="light"
          color="gray"
          leftSection={<IconShieldCheck size={14} />}
          onClick={() => setPresupuestoAAuditar(presupuesto)}
        >
          Auditoría
        </Button>
      )}
      <Button
        size="xs"
        color="teal"
        leftSection={<IconGavel size={14} />}
        onClick={() => setPresupuestoADecidir(presupuesto)}
        disabled={presupuesto.estados_posibles.length === 0}
      >
        Decidir
      </Button>
    </>
  );

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md">
        <Title order={2}>Presupuestos</Title>
      </Group>

      {!cargando && presupuestos.length > 0 && (
        <Group mb="md" align="flex-end" wrap="wrap">
          <TextInput
            label="Reclamo"
            placeholder="Ej: REC-00000034 o 34"
            value={busquedaReclamo}
            onChange={(event) => setBusquedaReclamo(event.currentTarget.value)}
            w={{ base: '100%', sm: 180 }}
          />
          <StatusFilterPopover
            value={estadosFiltro}
            onChange={setEstadosFiltro}
            estados={ESTADOS}
            etiquetaPorEstado={etiquetaPorEstado}
          />
          <DatePickerInput
            type="range"
            allowSingleDateInRange
            label="Fecha"
            placeholder="Seleccioná un rango"
            value={rangoFechas}
            onChange={setRangoFechas}
            valueFormat="DD/MM/YYYY"
            clearable
            w={{ base: '100%', sm: 260 }}
          />
          {hayFiltrosActivos && (
            <Button variant="subtle" onClick={limpiarFiltros}>
              Limpiar filtros
            </Button>
          )}
        </Group>
      )}

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && presupuestos.length === 0 && (
        <Text c="dimmed">Todavía no hay presupuestos registrados.</Text>
      )}

      {!cargando && presupuestos.length > 0 && presupuestosFiltrados.length === 0 && (
        <Text c="dimmed">Ningún presupuesto coincide con los filtros seleccionados.</Text>
      )}

      {!cargando && presupuestosFiltrados.length > 0 && esMobile && (
        <Stack gap="sm">
          {presupuestosFiltrados.map((presupuesto) => {
            const anteriores = ofertasAnteriores.get(presupuesto.id) ?? [];
            return (
              <TarjetaMovil
                key={presupuesto.id}
                onClick={() => setPresupuestoSeleccionado(presupuesto)}
                titulo={`${formatearIdReclamo(presupuesto.reclamo.id)} · ${presupuesto.reclamo.nombre_escuela}`}
                badges={
                  <>
                    <BudgetStatusBadge estado={presupuesto.estado} />
                    {badgesOferta(presupuesto, anteriores)}
                  </>
                }
                campos={[
                  { etiqueta: 'Contratista', valor: presupuesto.contratista.nombre_empresa },
                  { etiqueta: 'Monto', valor: formatoMoneda.format(Number(presupuesto.monto)) },
                  { etiqueta: 'Fecha', valor: new Date(presupuesto.fecha).toLocaleString('es-AR') },
                  {
                    etiqueta: 'Observaciones',
                    valor: presupuesto.observaciones && (
                      <Text size="sm" lineClamp={2}>
                        {presupuesto.observaciones}
                      </Text>
                    ),
                  },
                ]}
                pie={botonesPresupuesto(presupuesto)}
              />
            );
          })}
        </Stack>
      )}

      {!cargando && presupuestosFiltrados.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={900}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>ID Reclamo</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Contratista</Table.Th>
                <Table.Th>Monto</Table.Th>
                <Table.Th miw={130}>Estado</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Observaciones</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {presupuestosFiltrados.map((presupuesto) => {
                const anteriores = ofertasAnteriores.get(presupuesto.id) ?? [];
                return (
                  <Table.Tr
                    key={presupuesto.id}
                    onClick={() => setPresupuestoSeleccionado(presupuesto)}
                    style={{ cursor: 'pointer' }}
                  >
                    <Table.Td w={40}>
                      <ActionIcon variant="subtle" size="sm" aria-label="Ver ítems">
                        <IconListDetails size={16} />
                      </ActionIcon>
                    </Table.Td>
                    <Table.Td>{formatearIdReclamo(presupuesto.reclamo.id)}</Table.Td>
                    <Table.Td>{presupuesto.reclamo.nombre_escuela}</Table.Td>
                    <Table.Td>
                      {presupuesto.contratista.nombre_empresa}
                      {badgesOferta(presupuesto, anteriores)}
                    </Table.Td>
                    <Table.Td>{formatoMoneda.format(Number(presupuesto.monto))}</Table.Td>
                    <Table.Td miw={130}>
                      <BudgetStatusBadge estado={presupuesto.estado} />
                    </Table.Td>
                    <Table.Td>{new Date(presupuesto.fecha).toLocaleString('es-AR')}</Table.Td>
                    <Table.Td>
                      {presupuesto.observaciones ? (
                        <Text truncate="end" maw={200} title={presupuesto.observaciones}>
                          {presupuesto.observaciones}
                        </Text>
                      ) : (
                        <Text c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td onClick={(e) => e.stopPropagation()}>
                      <Group gap="xs" wrap="nowrap" justify="flex-end">
                        {botonesPresupuesto(presupuesto)}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <BudgetItemsModal
        presupuesto={presupuestoSeleccionado}
        onClose={() => setPresupuestoSeleccionado(null)}
        onDecidido={() => {
          setPresupuestoSeleccionado(null);
          cargar();
        }}
      />

      <BudgetAuditModal
        presupuesto={presupuestoAAuditar}
        onClose={() => setPresupuestoAAuditar(null)}
      />

      {/* Recarga la lista entera y no la fila: aprobar uno deja a los otros del mismo
          reclamo como no seleccionados. */}
      <DecideBudgetModal
        presupuesto={presupuestoADecidir}
        onClose={() => setPresupuestoADecidir(null)}
        onDecidido={cargar}
      />
    </Container>
  );
}
