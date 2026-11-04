import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Alert,
  Badge,
  Button,
  Container,
  Flex,
  Group,
  Loader,
  Menu,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconAlertTriangle, IconSearch, IconUserCheck } from '@tabler/icons-react';

import { RowActionsMenu } from '../../components/RowActionsMenu';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import {
  darDeBajaContratista,
  listarContratistas,
  reactivarContratista,
} from '../../api/contratistas';
import { porCalificacion, porNombre } from '../../utils/contratistas';
import { normalizarTexto } from '../../utils/filtros';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { claveTelefono, esTelefonoSimulado, formatearTelefono } from '../../utils/telefonos';
import { CalificacionContratista } from './CalificacionContratista';
import { DadoDeBajaBadge } from './DadoDeBajaBadge';

const ORDENES = [
  { value: 'nombre', label: 'Nombre (A-Z)' },
  { value: 'calificacion', label: 'Mejor calificación' },
  { value: 'especialidad', label: 'Especialidad' },
];

const porEspecialidad = (a, b) => a.especialidad.localeCompare(b.especialidad, 'es');

const COMPARADORES = {
  nombre: porNombre,
  calificacion: (a, b) => porCalificacion(a, b) || porNombre(a, b),
  especialidad: (a, b) => porEspecialidad(a, b) || porCalificacion(a, b) || porNombre(a, b),
};

const cantidadContratistas = (n) => (n === 1 ? '1 contratista' : `${n} contratistas`);

function coincideBusqueda(contratista, busqueda) {
  const termino = normalizarTexto(busqueda);
  if (!termino) return true;
  const textos = [contratista.nombre_empresa, contratista.especialidad, contratista.direccion];
  if (textos.some((texto) => normalizarTexto(texto).includes(termino))) return true;
  const digitos = busqueda.replace(/\D/g, '');
  return digitos.length >= 3 && contratista.telefono.replace(/\D/g, '').includes(digitos);
}

// El bot reconoce al contratista por el número, así que dos fichas activas con el mismo
// teléfono se pueden confundir. Los dados de baja no cuentan: ya no se los convoca.
function repetidosPorTelefono(contratistas) {
  const porClave = new Map();
  for (const c of contratistas) {
    const clave = claveTelefono(c.telefono);
    if (c.fecha_baja || !clave) continue;
    porClave.set(clave, [...(porClave.get(clave) ?? []), c]);
  }
  const repetidos = new Map();
  for (const grupo of porClave.values()) {
    if (grupo.length < 2) continue;
    for (const c of grupo)
      repetidos.set(
        c.id,
        grupo.filter((otro) => otro.id !== c.id),
      );
  }
  return repetidos;
}

function EspecialidadBadge({ especialidad }) {
  return (
    <Badge size="sm" variant="light" color="gray" tt="none">
      {especialidad}
    </Badge>
  );
}

function Empresa({ contratista }) {
  return (
    <div style={{ minWidth: 0 }}>
      <Group gap="xs" wrap="nowrap">
        <Text fw={600} size="sm">
          {contratista.nombre_empresa}
        </Text>
        {contratista.fecha_baja && <DadoDeBajaBadge />}
      </Group>
      {contratista.observaciones_calificacion && (
        <Text
          size="xs"
          c="dimmed"
          mt={2}
          maw={360}
          lineClamp={2}
          title={contratista.observaciones_calificacion}
        >
          {contratista.observaciones_calificacion}
        </Text>
      )}
    </div>
  );
}

function Telefono({ contratista, repetidoCon }) {
  const simulado = esTelefonoSimulado(contratista.telefono);
  return (
    <Stack gap={4} align="flex-start">
      <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
        {formatearTelefono(contratista.telefono)}
      </Text>
      {(simulado || repetidoCon) && (
        <Group gap={4}>
          {simulado && (
            <Badge size="xs" variant="outline" color="gray" tt="none">
              Simulado
            </Badge>
          )}
          {repetidoCon && (
            <Tooltip
              multiline
              w={280}
              withArrow
              events={{ hover: true, focus: true, touch: true }}
              label={`Mismo teléfono que ${repetidoCon
                .map((otro) => `${otro.nombre_empresa} (${otro.direccion})`)
                .join(', ')}. El bot reconoce al contratista por el número y los puede confundir.`}
            >
              <Badge
                size="xs"
                variant="light"
                color="orange"
                tt="none"
                leftSection={<IconAlertTriangle size={10} />}
              >
                Teléfono repetido
              </Badge>
            </Tooltip>
          )}
        </Group>
      )}
    </Stack>
  );
}

export function ContractorsListPage() {
  const navigate = useNavigate();
  const [contratistas, setContratistas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [verDadosDeBaja, setVerDadosDeBaja] = useState(false);
  const [busqueda, setBusqueda] = useState('');
  const [orden, setOrden] = useState('nombre');
  const [aDarDeBaja, setADarDeBaja] = useState(null);
  const [errorBaja, setErrorBaja] = useState(null);
  const [procesandoId, setProcesandoId] = useState(null);

  useEffect(() => {
    listarContratistas({ incluirBaja: true })
      .then(setContratistas)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const cantidadDadosDeBaja = contratistas.filter((c) => c.fecha_baja).length;
  const alcance = verDadosDeBaja ? contratistas : contratistas.filter((c) => !c.fecha_baja);

  const visibles = useMemo(
    () =>
      contratistas
        .filter((c) => (verDadosDeBaja || !c.fecha_baja) && coincideBusqueda(c, busqueda))
        .sort(COMPARADORES[orden]),
    [contratistas, verDadosDeBaja, busqueda, orden],
  );

  const repetidos = useMemo(() => repetidosPorTelefono(contratistas), [contratistas]);

  const reemplazar = (actualizado) =>
    setContratistas((actuales) => actuales.map((c) => (c.id === actualizado.id ? actualizado : c)));

  const cerrarBaja = () => {
    setADarDeBaja(null);
    setErrorBaja(null);
  };

  const confirmarBaja = async () => {
    const contratista = aDarDeBaja;
    setProcesandoId(contratista.id);
    setErrorBaja(null);
    try {
      await darDeBajaContratista(contratista.id);
      reemplazar({ ...contratista, fecha_baja: new Date().toISOString() });
      notifySuccess(`${contratista.nombre_empresa} quedó dado de baja.`);
      cerrarBaja();
    } catch (err) {
      setErrorBaja(err.message);
    } finally {
      setProcesandoId(null);
    }
  };

  const handleReactivar = async (contratista) => {
    setProcesandoId(contratista.id);
    try {
      reemplazar(await reactivarContratista(contratista.id));
      notifySuccess(`${contratista.nombre_empresa} volvió a estar activo.`);
    } catch (err) {
      notifyError(err?.message);
    } finally {
      setProcesandoId(null);
    }
  };

  const esMobile = useEsMobile();

  const acciones = (contratista) =>
    contratista.fecha_baja ? (
      <RowActionsMenu
        onEdit={() => navigate(`/contratistas/${contratista.id}/editar`)}
        extraItems={
          <Menu.Item
            leftSection={<IconUserCheck size={14} />}
            onClick={() => handleReactivar(contratista)}
            disabled={procesandoId === contratista.id}
          >
            Reactivar
          </Menu.Item>
        }
      />
    ) : (
      <RowActionsMenu
        onEdit={() => navigate(`/contratistas/${contratista.id}/editar`)}
        onDelete={() => setADarDeBaja(contratista)}
        deleting={procesandoId === contratista.id}
        deleteLabel="Dar de baja"
        deletingLabel="Dando de baja..."
      />
    );

  const cantidadRepetidos = alcance.filter((c) => repetidos.has(c.id)).length;

  let mensajeVacio = 'No hay contratistas que coincidan con la búsqueda.';
  if (contratistas.length === 0) mensajeVacio = 'Todavía no hay contratistas registrados.';
  else if (alcance.length === 0) mensajeVacio = 'No hay contratistas activos.';

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Title order={2}>Contratistas</Title>
        <Button onClick={() => navigate('/contratistas/nuevo')}>+ Nuevo Contratista</Button>
      </Group>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && contratistas.length > 0 && (
        <Stack gap="xs" mb="sm">
          <Flex
            gap="sm"
            direction={{ base: 'column', sm: 'row' }}
            align={{ base: 'stretch', sm: 'center' }}
          >
            <TextInput
              placeholder="Buscar por nombre, especialidad, teléfono o dirección"
              aria-label="Buscar contratista"
              leftSection={<IconSearch size={16} />}
              value={busqueda}
              onChange={(e) => setBusqueda(e.currentTarget.value)}
              style={{ flex: 1 }}
            />
            <Select
              aria-label="Ordenar contratistas"
              data={ORDENES}
              value={orden}
              onChange={(v) => setOrden(v || 'nombre')}
              allowDeselect={false}
              w={{ base: '100%', sm: 200 }}
            />
            {cantidadDadosDeBaja > 0 && (
              <Switch
                label={`Mostrar dados de baja (${cantidadDadosDeBaja})`}
                checked={verDadosDeBaja}
                onChange={(event) => setVerDadosDeBaja(event.currentTarget.checked)}
              />
            )}
          </Flex>
          {alcance.length > 0 && (
            <Text size="sm" c="dimmed">
              {visibles.length === alcance.length
                ? cantidadContratistas(alcance.length)
                : `${visibles.length} de ${cantidadContratistas(alcance.length)}`}
              {cantidadRepetidos > 0 && (
                <Text span size="sm" c="orange.7">
                  {` · ${cantidadRepetidos} con teléfono repetido`}
                </Text>
              )}
            </Text>
          )}
        </Stack>
      )}

      {!cargando && visibles.length === 0 && <Text c="dimmed">{mensajeVacio}</Text>}

      {!cargando && visibles.length > 0 && esMobile && (
        <Stack gap="sm">
          {visibles.map((contratista) => (
            <TarjetaMovil
              key={contratista.id}
              titulo={contratista.nombre_empresa}
              acciones={acciones(contratista)}
              badges={
                <>
                  <EspecialidadBadge especialidad={contratista.especialidad} />
                  {contratista.fecha_baja && <DadoDeBajaBadge />}
                </>
              }
              campos={[
                {
                  etiqueta: 'Calificación',
                  valor: (
                    <CalificacionContratista
                      calificacion={contratista.calificacion}
                      align="flex-start"
                    />
                  ),
                },
                { etiqueta: 'Observación', valor: contratista.observaciones_calificacion },
                {
                  etiqueta: 'Teléfono',
                  valor: (
                    <Telefono
                      contratista={contratista}
                      repetidoCon={repetidos.get(contratista.id)}
                    />
                  ),
                },
                { etiqueta: 'Dirección', valor: contratista.direccion },
              ]}
            />
          ))}
        </Stack>
      )}

      {!cargando && visibles.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={800}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Empresa</Table.Th>
                <Table.Th>Especialidad</Table.Th>
                <Table.Th>Calificación</Table.Th>
                <Table.Th>Teléfono</Table.Th>
                <Table.Th>Dirección</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visibles.map((contratista) => (
                <Table.Tr key={contratista.id}>
                  <Table.Td>
                    <Empresa contratista={contratista} />
                  </Table.Td>
                  <Table.Td>
                    <EspecialidadBadge especialidad={contratista.especialidad} />
                  </Table.Td>
                  <Table.Td>
                    <CalificacionContratista
                      calificacion={contratista.calificacion}
                      align="flex-start"
                    />
                  </Table.Td>
                  <Table.Td>
                    <Telefono
                      contratista={contratista}
                      repetidoCon={repetidos.get(contratista.id)}
                    />
                  </Table.Td>
                  <Table.Td>{contratista.direccion}</Table.Td>
                  <Table.Td>{acciones(contratista)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={aDarDeBaja !== null}
        onClose={cerrarBaja}
        title={aDarDeBaja ? `Dar de baja a ${aDarDeBaja.nombre_empresa}` : ''}
        centered
      >
        <Stack>
          <Text size="sm">
            No se lo va a poder convocar ni va a poder cargar presupuestos. Sus presupuestos y
            visitas anteriores se conservan, y podés reactivarlo cuando quieras.
          </Text>
          {errorBaja && (
            <Alert color="red" title="No se pudo dar de baja">
              {errorBaja}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={cerrarBaja}>
              Cancelar
            </Button>
            <Button
              color="red"
              onClick={confirmarBaja}
              loading={aDarDeBaja !== null && procesandoId === aDarDeBaja.id}
            >
              Dar de baja
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
