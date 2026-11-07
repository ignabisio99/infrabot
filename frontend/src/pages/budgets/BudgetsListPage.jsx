import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Container,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconArrowUpRight, IconGavel, IconListDetails, IconShieldCheck } from '@tabler/icons-react';

import { listarPresupuestos } from '../../api/presupuestos';
import { nombreCortoEscuela } from '../../utils/escuelas';
import { formatearIdReclamo } from '../../utils/ids';
import { fechaEnRango, idCoincideConBusqueda } from '../../utils/filtros';
import { formatoFechaHoraCorta, formatoMoneda } from '../../utils/formatters';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { StatusBadge } from '../claims/StatusBadge';
import { StatusFilterPopover } from '../claims/StatusFilterPopover';
import { DadoDeBajaBadge } from '../contractors/DadoDeBajaBadge';
import { BudgetAuditModal } from './BudgetAuditModal';
import { BudgetItemsModal } from './BudgetItemsModal';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { masBarata, ordenarOfertas, porcentajeSobre } from './comparacion';
import { DecideBudgetModal } from './DecideBudgetModal';
import { ESTADOS, estaVigente, etiquetaPorEstado } from './estados';

const COLUMNAS = 7;
// Se pagina por reclamo y no por oferta, para no partir las ofertas de un reclamo en dos
// páginas.
const RECLAMOS_POR_PAGINA = 10;

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

// La más barata se calcula sobre todas las ofertas del reclamo y no sólo las filtradas:
// filtrar por "Recibido" no tiene que esconder que ya hay una aprobada.
function masBarataPorReclamo(presupuestos) {
  const porReclamo = new Map();
  for (const p of presupuestos) {
    porReclamo.set(p.reclamo.id, [...(porReclamo.get(p.reclamo.id) ?? []), p]);
  }
  return new Map([...porReclamo].map(([id, ofertas]) => [id, masBarata(ofertas)]));
}

function agruparPorReclamo(presupuestos) {
  const grupos = new Map();
  for (const p of presupuestos) {
    if (!grupos.has(p.reclamo.id)) grupos.set(p.reclamo.id, { reclamo: p.reclamo, ofertas: [] });
    grupos.get(p.reclamo.id).ofertas.push(p);
  }
  return [...grupos.values()].map((g) => ({ ...g, ofertas: ordenarOfertas(g.ofertas) }));
}

function Monto({ presupuesto, barata }) {
  const esLaMasBarata = barata?.id === presupuesto.id;
  const diferencia =
    barata && !esLaMasBarata && estaVigente(presupuesto)
      ? porcentajeSobre(presupuesto, barata)
      : null;
  return (
    <Stack gap={2} align="flex-start">
      <Text size="sm" fw={600} style={{ whiteSpace: 'nowrap' }}>
        {formatoMoneda.format(Number(presupuesto.monto))}
      </Text>
      {esLaMasBarata && (
        <Badge size="xs" variant="light" color="teal" tt="none">
          Más barata
        </Badge>
      )}
      {diferencia != null && (
        <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
          +{diferencia}% que la más barata
        </Text>
      )}
    </Stack>
  );
}

function textoCantidadOfertas(cantidad, total) {
  if (cantidad < total) return `${cantidad} de ${total} ofertas`;
  return cantidad === 1 ? '1 oferta' : `${cantidad} ofertas`;
}

function EncabezadoReclamo({ reclamo, cantidad, total, onVer }) {
  return (
    <Group justify="space-between" wrap="nowrap" gap="sm">
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Text ff="monospace" size="sm" fw={600} style={{ whiteSpace: 'nowrap' }}>
          {formatearIdReclamo(reclamo.id)}
        </Text>
        <Text size="sm" fw={600} truncate title={reclamo.nombre_escuela}>
          {nombreCortoEscuela(reclamo.nombre_escuela)}
        </Text>
        <StatusBadge estado={reclamo.estado} variant="light" size="sm" />
        <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
          {textoCantidadOfertas(cantidad, total)}
        </Text>
      </Group>
      <Button
        variant="subtle"
        size="compact-xs"
        rightSection={<IconArrowUpRight size={14} />}
        onClick={onVer}
      >
        Ver reclamo
      </Button>
    </Group>
  );
}

export function BudgetsListPage() {
  const navigate = useNavigate();
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [presupuestoSeleccionado, setPresupuestoSeleccionado] = useState(null);
  const [presupuestoAAuditar, setPresupuestoAAuditar] = useState(null);
  const [presupuestoADecidir, setPresupuestoADecidir] = useState(null);
  const ofertasAnteriores = useMemo(() => ofertasAnterioresPorId(presupuestos), [presupuestos]);
  const masBaratas = useMemo(() => masBarataPorReclamo(presupuestos), [presupuestos]);
  // Contra el total sin filtrar: con un filtro puesto, el encabezado avisa que el reclamo
  // tiene más ofertas que las que se ven.
  const totalOfertas = useMemo(() => {
    const totales = new Map();
    for (const p of presupuestos) totales.set(p.reclamo.id, (totales.get(p.reclamo.id) ?? 0) + 1);
    return totales;
  }, [presupuestos]);

  const [busquedaReclamo, setBusquedaReclamo] = useState('');
  const [estadosFiltro, setEstadosFiltro] = useState([]);
  const [rangoFechas, setRangoFechas] = useState([null, null]);
  const [pagina, setPagina] = useState(1);

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

  const grupos = useMemo(() => agruparPorReclamo(presupuestosFiltrados), [presupuestosFiltrados]);

  const filtroActual = `${busquedaReclamo}|${estadosFiltro}|${rangoFechas[0]}|${rangoFechas[1]}`;
  const [filtroPrevio, setFiltroPrevio] = useState(filtroActual);
  if (filtroActual !== filtroPrevio) {
    setFiltroPrevio(filtroActual);
    setPagina(1);
  }

  const totalPaginas = Math.ceil(grupos.length / RECLAMOS_POR_PAGINA);
  // Decidir una oferta con un filtro de estado puesto la saca del listado: si era lo único
  // de la última página, sin esto quedaría una página vacía.
  const paginaVisible = Math.min(pagina, Math.max(totalPaginas, 1));
  const gruposPagina = grupos.slice(
    (paginaVisible - 1) * RECLAMOS_POR_PAGINA,
    paginaVisible * RECLAMOS_POR_PAGINA,
  );
  const verReclamo = (id) => navigate(`/reclamos?abrir=${id}`);

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

  const puedeAuditar = (presupuesto) => presupuesto.estado !== 'APROBADO';
  const puedeDecidir = (presupuesto) => presupuesto.estados_posibles.length > 0;

  // Lugares fijos para que el botón y el ícono queden alineados entre filas aunque
  // alguna no tenga una de las dos acciones.
  const accionesPresupuesto = (presupuesto) => (
    <Group gap={4} wrap="nowrap" justify="flex-end">
      <Box w={92}>
        {puedeDecidir(presupuesto) && (
          <Button
            size="xs"
            color="teal"
            fullWidth
            leftSection={<IconGavel size={14} />}
            onClick={() => setPresupuestoADecidir(presupuesto)}
          >
            Decidir
          </Button>
        )}
      </Box>
      <Box w={28}>
        {puedeAuditar(presupuesto) && (
          <Tooltip label="Auditoría de IA" withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              aria-label="Auditoría"
              onClick={() => setPresupuestoAAuditar(presupuesto)}
            >
              <IconShieldCheck size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Box>
    </Group>
  );

  const botonesMovil = (presupuesto) =>
    (puedeDecidir(presupuesto) || puedeAuditar(presupuesto)) && (
      <>
        {puedeAuditar(presupuesto) && (
          <Button
            size="xs"
            variant="default"
            leftSection={<IconShieldCheck size={14} />}
            onClick={() => setPresupuestoAAuditar(presupuesto)}
          >
            Auditoría
          </Button>
        )}
        {puedeDecidir(presupuesto) && (
          <Button
            size="xs"
            color="teal"
            leftSection={<IconGavel size={14} />}
            onClick={() => setPresupuestoADecidir(presupuesto)}
          >
            Decidir
          </Button>
        )}
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
        <Stack gap="lg">
          {gruposPagina.map(({ reclamo, ofertas }) => (
            <Stack key={reclamo.id} gap="xs">
              <EncabezadoReclamo
                reclamo={reclamo}
                cantidad={ofertas.length}
                total={totalOfertas.get(reclamo.id)}
                onVer={() => verReclamo(reclamo.id)}
              />
              {ofertas.map((presupuesto) => {
                const anteriores = ofertasAnteriores.get(presupuesto.id) ?? [];
                return (
                  <TarjetaMovil
                    key={presupuesto.id}
                    onClick={() => setPresupuestoSeleccionado(presupuesto)}
                    titulo={presupuesto.contratista.nombre_empresa}
                    badges={
                      <>
                        <BudgetStatusBadge estado={presupuesto.estado} />
                        {presupuesto.contratista.fecha_baja && <DadoDeBajaBadge size="xs" />}
                        {badgesOferta(presupuesto, anteriores)}
                      </>
                    }
                    campos={[
                      {
                        etiqueta: 'Monto',
                        valor: (
                          <Monto presupuesto={presupuesto} barata={masBaratas.get(reclamo.id)} />
                        ),
                      },
                      { etiqueta: 'Fecha', valor: formatoFechaHoraCorta(presupuesto.fecha) },
                      {
                        etiqueta: 'Observaciones',
                        valor: presupuesto.observaciones && (
                          <Text size="sm" lineClamp={2}>
                            {presupuesto.observaciones}
                          </Text>
                        ),
                      },
                    ]}
                    pie={botonesMovil(presupuesto)}
                  />
                );
              })}
            </Stack>
          ))}
        </Stack>
      )}

      {!cargando && presupuestosFiltrados.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={900}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>Contratista</Table.Th>
                <Table.Th>Monto</Table.Th>
                <Table.Th miw={130}>Estado</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Observaciones</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            {gruposPagina.map(({ reclamo, ofertas }) => (
              <Table.Tbody key={reclamo.id}>
                <Table.Tr bg="var(--mantine-color-gray-0)">
                  <Table.Td colSpan={COLUMNAS}>
                    <EncabezadoReclamo
                      reclamo={reclamo}
                      cantidad={ofertas.length}
                      total={totalOfertas.get(reclamo.id)}
                      onVer={() => verReclamo(reclamo.id)}
                    />
                  </Table.Td>
                </Table.Tr>
                {ofertas.map((presupuesto) => {
                  const anteriores = ofertasAnteriores.get(presupuesto.id) ?? [];
                  const cerrada = ['RECHAZADO', 'NO_SELECCIONADO'].includes(presupuesto.estado);
                  return (
                    <Table.Tr
                      key={presupuesto.id}
                      onClick={() => setPresupuestoSeleccionado(presupuesto)}
                      style={{ cursor: 'pointer', opacity: cerrada ? 0.6 : undefined }}
                    >
                      <Table.Td w={40}>
                        <ActionIcon variant="subtle" size="sm" aria-label="Ver ítems">
                          <IconListDetails size={16} />
                        </ActionIcon>
                      </Table.Td>
                      <Table.Td>
                        {presupuesto.contratista.nombre_empresa}
                        {presupuesto.contratista.fecha_baja && <DadoDeBajaBadge ml={6} size="xs" />}
                        {badgesOferta(presupuesto, anteriores)}
                      </Table.Td>
                      <Table.Td>
                        <Monto presupuesto={presupuesto} barata={masBaratas.get(reclamo.id)} />
                      </Table.Td>
                      <Table.Td miw={130}>
                        <BudgetStatusBadge estado={presupuesto.estado} />
                      </Table.Td>
                      <Table.Td style={{ whiteSpace: 'nowrap' }}>
                        {formatoFechaHoraCorta(presupuesto.fecha)}
                      </Table.Td>
                      <Table.Td>
                        {presupuesto.observaciones ? (
                          <Text
                            size="sm"
                            truncate="end"
                            maw={220}
                            title={presupuesto.observaciones}
                          >
                            {presupuesto.observaciones}
                          </Text>
                        ) : (
                          <Text c="dimmed">—</Text>
                        )}
                      </Table.Td>
                      <Table.Td onClick={(e) => e.stopPropagation()}>
                        {accionesPresupuesto(presupuesto)}
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            ))}
          </Table>
        </Table.ScrollContainer>
      )}

      {!cargando && totalPaginas > 1 && (
        <Group justify="center" mt="md">
          <Pagination total={totalPaginas} value={paginaVisible} onChange={setPagina} />
        </Group>
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
