import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import {
  ActionIcon,
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconExchange, IconEye } from '@tabler/icons-react';

import { RowActionsMenu } from '../../components/RowActionsMenu';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { eliminarReclamo, listarReclamos } from '../../api/reclamos';
import { esInspector } from '../../utils/auth';
import { fechaEnRango, idCoincideConBusqueda } from '../../utils/filtros';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { ChangeStatusModal } from './ChangeStatusModal';
import { ClaimDetailDrawer } from './ClaimDetailDrawer';
import { PriorityBadge } from './PriorityBadge';
import { StatusBadge } from './StatusBadge';
import { StatusFilterPopover } from './StatusFilterPopover';
import { ESTADOS } from './estados';

const opcionesPrioridad = [
  { value: '', label: 'Todas' },
  { value: 'BAJA', label: 'Baja' },
  { value: 'MEDIA', label: 'Media' },
  { value: 'ALTA', label: 'Alta' },
];

const POR_PAGINA = 10;

// El Dashboard enlaza acá con los filtros ya elegidos: uno o varios estados separados por
// coma (/reclamos?estado=EN_EVALUACION, /reclamos?estado=APROBADO,EN_EJECUCION), la
// prioridad (&prioridad=ALTA), la categoría (&categoria=Gas) y el ID
// (/reclamos?busqueda=REC-00000007). Los estados y prioridades que no existan se ignoran
// en vez de dejar la lista vacía sin explicación.
function estadosDeParams(searchParams) {
  const estados = new Set(searchParams.get('estado')?.split(',') ?? []);
  return [...estados].filter((estado) => ESTADOS.includes(estado));
}

function prioridadDeParams(searchParams) {
  const prioridad = searchParams.get('prioridad') ?? '';
  return opcionesPrioridad.some((opcion) => opcion.value === prioridad) ? prioridad : '';
}

function categoriaDeParams(searchParams) {
  return searchParams.get('categoria') ?? '';
}

function busquedaDeParams(searchParams) {
  return searchParams.get('busqueda') ?? '';
}

// `?abrir=34` abre el detalle de ese reclamo al entrar.
function reclamoAbrirDeParams(searchParams) {
  const id = Number(searchParams.get('abrir'));
  return searchParams.get('abrir') && !Number.isNaN(id) ? id : null;
}

export function ClaimsListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [reclamos, setReclamos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [reclamoIdSeleccionado, setReclamoIdSeleccionado] = useState(() =>
    reclamoAbrirDeParams(searchParams),
  );
  const [reclamoParaCambiarEstado, setReclamoParaCambiarEstado] = useState(null);

  const [prioridadFiltro, setPrioridadFiltro] = useState(() => prioridadDeParams(searchParams));
  const [categoriaFiltro, setCategoriaFiltro] = useState(() => categoriaDeParams(searchParams));
  const [estadosFiltro, setEstadosFiltro] = useState(() => estadosDeParams(searchParams));
  const [rangoFechas, setRangoFechas] = useState([null, null]);
  const [busquedaId, setBusquedaId] = useState(() => busquedaDeParams(searchParams));
  const [pagina, setPagina] = useState(1);

  // Ir a /reclamos desde el menú lateral no remonta la página: es la misma ruta, así que
  // los filtros seguirían aplicados aunque la URL ya no los tenga, y el listado saldría
  // filtrado sin que nadie lo haya pedido. Mismo patrón que el reseteo de página de más
  // abajo: ajustar el estado en el render, no en un effect.
  //
  // Se reinician todos los filtros y no sólo los que viajan en la URL: entrar por un
  // link (o volver a /reclamos pelado) pide esa vista, no esa vista más el rango de
  // fechas que hubiera quedado del listado anterior.
  const paramsActuales = searchParams.toString();
  const [paramsPrevios, setParamsPrevios] = useState(paramsActuales);
  if (paramsActuales !== paramsPrevios) {
    setParamsPrevios(paramsActuales);
    setEstadosFiltro(estadosDeParams(searchParams));
    setBusquedaId(busquedaDeParams(searchParams));
    setPrioridadFiltro(prioridadDeParams(searchParams));
    setCategoriaFiltro(categoriaDeParams(searchParams));
    setRangoFechas([null, null]);
    const abrir = reclamoAbrirDeParams(searchParams);
    if (abrir !== null) setReclamoIdSeleccionado(abrir);
  }

  useEffect(() => {
    listarReclamos()
      .then(setReclamos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const reclamosFiltrados = useMemo(() => {
    return reclamos.filter((reclamo) => {
      if (prioridadFiltro && reclamo.prioridad !== prioridadFiltro) return false;
      if (categoriaFiltro && reclamo.categoria !== categoriaFiltro) return false;

      // Sin estados elegidos no se filtra: ninguno tildado es "todos".
      if (estadosFiltro.length > 0 && !estadosFiltro.includes(reclamo.estado)) return false;

      if (!idCoincideConBusqueda(reclamo.id, busquedaId)) return false;

      return fechaEnRango(reclamo.fecha_creacion, rangoFechas);
    });
  }, [reclamos, prioridadFiltro, categoriaFiltro, estadosFiltro, rangoFechas, busquedaId]);

  const opcionesCategoria = useMemo(
    // La elegida va aunque ningún reclamo la tenga, para que el Select la muestre y se
    // pueda limpiar.
    () =>
      [...new Set([...reclamos.map((reclamo) => reclamo.categoria), categoriaFiltro])]
        .filter(Boolean)
        .sort(),
    [reclamos, categoriaFiltro],
  );

  const hayFiltrosActivos =
    prioridadFiltro !== '' ||
    categoriaFiltro !== '' ||
    estadosFiltro.length > 0 ||
    rangoFechas[0] !== null ||
    rangoFechas[1] !== null ||
    busquedaId !== '';

  const limpiarFiltros = () => {
    setPrioridadFiltro('');
    setCategoriaFiltro('');
    setEstadosFiltro([]);
    setRangoFechas([null, null]);
    setBusquedaId('');
  };

  const filtroActual = `${prioridadFiltro}|${categoriaFiltro}|${estadosFiltro}|${rangoFechas[0]}|${rangoFechas[1]}|${busquedaId}`;
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
      notifySuccess('El reclamo fue eliminado correctamente.');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  const handleEstadoCambiado = (reclamoActualizado) => {
    setReclamos((actuales) =>
      actuales.map((reclamo) =>
        reclamo.id === reclamoActualizado.id ? reclamoActualizado : reclamo,
      ),
    );
  };

  const soloLectura = esInspector();
  const esMobile = useEsMobile();

  const accionesReclamo = (reclamo) =>
    !soloLectura && (
      <RowActionsMenu
        onEdit={() => navigate(`/reclamos/${reclamo.id}/editar`)}
        onDelete={() => handleEliminar(reclamo.id)}
        deleting={eliminandoId === reclamo.id}
        extraItems={
          <Menu.Item
            leftSection={<IconExchange size={14} />}
            onClick={() => setReclamoParaCambiarEstado(reclamo)}
            disabled={reclamo.estados_posibles.length === 0}
          >
            Cambiar estado
          </Menu.Item>
        }
      />
    );

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Title order={2}>Reclamos</Title>
        {!soloLectura && (
          <Button onClick={() => navigate('/reclamos/nuevo')}>+ Nuevo Reclamo</Button>
        )}
      </Group>

      {!cargando && reclamos.length > 0 && (
        <Group mb="md" align="flex-end" wrap="wrap">
          <TextInput
            label="ID"
            placeholder="Ej: REC-00000034 o 34"
            value={busquedaId}
            onChange={(event) => setBusquedaId(event.currentTarget.value)}
            w={{ base: '100%', sm: 180 }}
          />
          <Select
            label="Prioridad"
            data={opcionesPrioridad}
            value={prioridadFiltro}
            onChange={(value) => setPrioridadFiltro(value ?? '')}
            w={{ base: '100%', sm: 160 }}
          />
          <Select
            label="Categoría"
            placeholder="Todas"
            data={opcionesCategoria}
            value={categoriaFiltro || null}
            onChange={(value) => setCategoriaFiltro(value ?? '')}
            clearable
            searchable
            nothingFoundMessage="Sin coincidencias"
            w={{ base: '100%', sm: 180 }}
          />
          <StatusFilterPopover value={estadosFiltro} onChange={setEstadosFiltro} />
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

      {!cargando && reclamos.length === 0 && (
        <Text c="dimmed">Todavía no hay reclamos registrados.</Text>
      )}

      {!cargando && reclamos.length > 0 && reclamosFiltrados.length === 0 && (
        <Text c="dimmed">Ningún reclamo coincide con los filtros seleccionados.</Text>
      )}

      {!cargando && reclamosFiltrados.length > 0 && esMobile && (
        <Stack gap="sm">
          {reclamosPagina.map((reclamo) => (
            <TarjetaMovil
              key={reclamo.id}
              onClick={() => setReclamoIdSeleccionado(reclamo.id)}
              titulo={
                <>
                  <Text span ff="monospace" size="sm" fw={600}>
                    {formatearIdReclamo(reclamo.id)}
                  </Text>{' '}
                  · {reclamo.nombre_escuela}
                </>
              }
              acciones={accionesReclamo(reclamo)}
              badges={
                <>
                  <StatusBadge estado={reclamo.estado} variant="light" />
                  <PriorityBadge prioridad={reclamo.prioridad} fz="sm" />
                </>
              }
              campos={[
                { etiqueta: 'Ubicación', valor: reclamo.ubicacion },
                { etiqueta: 'Categoría', valor: reclamo.categoria },
                {
                  etiqueta: 'Descripción',
                  valor: (
                    <Text size="sm" lineClamp={2}>
                      {reclamo.descripcion}
                    </Text>
                  ),
                },
                {
                  etiqueta: 'Fecha',
                  valor: new Date(reclamo.fecha_creacion).toLocaleString('es-AR'),
                },
              ]}
            />
          ))}
        </Stack>
      )}

      {!cargando && reclamosFiltrados.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={1000}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>ID</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Ubicación</Table.Th>
                <Table.Th>Prioridad</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Categoría</Table.Th>
                <Table.Th>Descripción</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {reclamosPagina.map((reclamo) => (
                <Table.Tr
                  key={reclamo.id}
                  onClick={() => setReclamoIdSeleccionado(reclamo.id)}
                  style={{ cursor: 'pointer' }}
                >
                  <Table.Td w={40}>
                    <ActionIcon variant="subtle" size="sm" aria-label="Ver detalle">
                      <IconEye size={16} />
                    </ActionIcon>
                  </Table.Td>
                  <Table.Td>
                    <Text ff="monospace">{formatearIdReclamo(reclamo.id)}</Text>
                  </Table.Td>
                  <Table.Td>{reclamo.nombre_escuela}</Table.Td>
                  <Table.Td>{reclamo.ubicacion}</Table.Td>
                  <Table.Td>
                    <PriorityBadge prioridad={reclamo.prioridad} fz="sm" />
                  </Table.Td>
                  <Table.Td>
                    <Group gap={6} wrap="nowrap">
                      <StatusBadge estado={reclamo.estado} variant="light" />
                    </Group>
                  </Table.Td>
                  <Table.Td>{reclamo.categoria}</Table.Td>
                  <Table.Td>
                    <Text truncate="end" maw={240} title={reclamo.descripcion}>
                      {reclamo.descripcion}
                    </Text>
                  </Table.Td>
                  <Table.Td>{new Date(reclamo.fecha_creacion).toLocaleString('es-AR')}</Table.Td>
                  <Table.Td>{accionesReclamo(reclamo)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      {!cargando && totalPaginas > 1 && (
        <Group justify="center" mt="md">
          <Pagination total={totalPaginas} value={pagina} onChange={setPagina} />
        </Group>
      )}

      <ClaimDetailDrawer
        reclamoId={reclamoIdSeleccionado}
        onClose={() => setReclamoIdSeleccionado(null)}
        onAbrirReclamo={setReclamoIdSeleccionado}
        onReclamoActualizado={() => {
          listarReclamos()
            .then(setReclamos)
            .catch((err) => notifyError(err.message));
        }}
      />

      <ChangeStatusModal
        reclamo={reclamoParaCambiarEstado}
        onClose={() => setReclamoParaCambiarEstado(null)}
        onEstadoCambiado={handleEstadoCambiado}
      />
    </Container>
  );
}
