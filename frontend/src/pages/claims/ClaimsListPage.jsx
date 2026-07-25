import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Pagination,
  Select,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';

import { eliminarReclamo, listarReclamos } from '../../api/reclamos';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError } from '../../utils/notifications';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

const opcionesPrioridad = [
  { value: '', label: 'Todas' },
  { value: 'BAJA', label: 'Baja' },
  { value: 'MEDIA', label: 'Media' },
  { value: 'ALTA', label: 'Alta' },
];

const POR_PAGINA = 10;

// Los valores del DatePickerInput llegan como string "YYYY-MM-DD". Parsearlos con
// `new Date(string)` los interpreta como medianoche UTC y desfasa el día en timezones
// negativos (ej. UTC-3), por eso se arman a mano como fecha local.
function parsearFechaFiltro(valor) {
  if (!valor) return null;
  const [anio, mes, dia] = valor.split('-').map(Number);
  return new Date(anio, mes - 1, dia);
}

// Acepta "34", "0034", "REC-00000034", etc: se queda solo con los dígitos
// escritos y busca esa subcadena dentro del ID completo (con ceros a la izquierda).
function idCoincideConBusqueda(id, busqueda) {
  const digitos = busqueda.replace(/\D/g, '');
  if (!digitos) return true;
  return String(id).padStart(8, '0').includes(digitos);
}

export function ClaimsListPage() {
  const navigate = useNavigate();
  const [reclamos, setReclamos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);

  const [prioridadFiltro, setPrioridadFiltro] = useState('');
  const [rangoFechas, setRangoFechas] = useState([null, null]);
  const [busquedaId, setBusquedaId] = useState('');
  const [pagina, setPagina] = useState(1);

  useEffect(() => {
    listarReclamos()
      .then(setReclamos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const reclamosFiltrados = useMemo(() => {
    const desde = parsearFechaFiltro(rangoFechas[0]);
    const hasta = parsearFechaFiltro(rangoFechas[1]);

    return reclamos.filter((reclamo) => {
      if (prioridadFiltro && reclamo.prioridad !== prioridadFiltro) return false;

      if (!idCoincideConBusqueda(reclamo.id, busquedaId)) return false;

      const fecha = new Date(reclamo.fecha_creacion);

      if (desde && fecha < desde) return false;

      if (hasta) {
        const finDia = new Date(hasta);
        finDia.setHours(23, 59, 59, 999);
        if (fecha > finDia) return false;
      }

      return true;
    });
  }, [reclamos, prioridadFiltro, rangoFechas, busquedaId]);

  const hayFiltrosActivos =
    prioridadFiltro !== '' ||
    rangoFechas[0] !== null ||
    rangoFechas[1] !== null ||
    busquedaId !== '';

  const limpiarFiltros = () => {
    setPrioridadFiltro('');
    setRangoFechas([null, null]);
    setBusquedaId('');
  };

  const filtroActual = `${prioridadFiltro}|${rangoFechas[0]}|${rangoFechas[1]}|${busquedaId}`;
  const [filtroPrevio, setFiltroPrevio] = useState(filtroActual);
  if (filtroActual !== filtroPrevio) {
    setFiltroPrevio(filtroActual);
    setPagina(1);
  }

  const totalPaginas = Math.ceil(reclamosFiltrados.length / POR_PAGINA);
  const reclamosPagina = reclamosFiltrados.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);

  const handleEliminar = async (id) => {
    if (!window.confirm('¿Seguro que querés eliminar este reclamo?')) return;

    setEliminandoId(id);
    try {
      await eliminarReclamo(id);
      setReclamos((actuales) => actuales.filter((reclamo) => reclamo.id !== id));
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  return (
    <Container fluid py="xl">
      <Group justify="space-between" mb="md">
        <Title order={2}>Reclamos</Title>
        <Button onClick={() => navigate('/reclamos/nuevo')}>+ Nuevo Reclamo</Button>
      </Group>

      {!cargando && reclamos.length > 0 && (
        <Group mb="md" align="flex-end">
          <TextInput
            label="ID"
            placeholder="Ej: REC-00000034 o 34"
            value={busquedaId}
            onChange={(event) => setBusquedaId(event.currentTarget.value)}
            w={180}
          />
          <Select
            label="Prioridad"
            data={opcionesPrioridad}
            value={prioridadFiltro}
            onChange={(value) => setPrioridadFiltro(value ?? '')}
            w={160}
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
            w={260}
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

      {!cargando && reclamos.length === 0 && (
        <Text c="dimmed">Todavía no hay reclamos registrados.</Text>
      )}

      {!cargando && reclamos.length > 0 && reclamosFiltrados.length === 0 && (
        <Text c="dimmed">Ningún reclamo coincide con los filtros seleccionados.</Text>
      )}

      {!cargando && reclamosFiltrados.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Escuela</Table.Th>
              <Table.Th>Ubicación</Table.Th>
              <Table.Th>Prioridad</Table.Th>
              <Table.Th>Categoría</Table.Th>
              <Table.Th>Descripción</Table.Th>
              <Table.Th>Observaciones</Table.Th>
              <Table.Th>Fecha</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {reclamosPagina.map((reclamo) => (
              <Table.Tr key={reclamo.id}>
                <Table.Td>
                  <Text ff="monospace">{formatearIdReclamo(reclamo.id)}</Text>
                </Table.Td>
                <Table.Td>{reclamo.nombre_escuela}</Table.Td>
                <Table.Td>{reclamo.ubicacion}</Table.Td>
                <Table.Td>
                  <Badge color={colorPorPrioridad[reclamo.prioridad]}>{reclamo.prioridad}</Badge>
                </Table.Td>
                <Table.Td>{reclamo.categoria}</Table.Td>
                <Table.Td>
                  <Text truncate="end" maw={280} title={reclamo.descripcion}>
                    {reclamo.descripcion}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {reclamo.observaciones ? (
                    <Text truncate="end" maw={200} title={reclamo.observaciones}>
                      {reclamo.observaciones}
                    </Text>
                  ) : (
                    <Text c="dimmed">—</Text>
                  )}
                </Table.Td>
                <Table.Td>{new Date(reclamo.fecha_creacion).toLocaleString('es-AR')}</Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Button
                      variant="subtle"
                      size="xs"
                      onClick={() => navigate(`/reclamos/${reclamo.id}/editar`)}
                    >
                      Editar
                    </Button>
                    <Button
                      color="red"
                      variant="subtle"
                      size="xs"
                      loading={eliminandoId === reclamo.id}
                      onClick={() => handleEliminar(reclamo.id)}
                    >
                      Eliminar
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {!cargando && totalPaginas > 1 && (
        <Group justify="center" mt="md">
          <Pagination total={totalPaginas} value={pagina} onChange={setPagina} />
        </Group>
      )}
    </Container>
  );
}
