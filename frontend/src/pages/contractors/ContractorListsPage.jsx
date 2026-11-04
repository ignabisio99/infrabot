import { useEffect, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Button,
  Card,
  Container,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconPlus, IconTrash, IconUsersGroup } from '@tabler/icons-react';

import { listarContratistas } from '../../api/contratistas';
import { crearLista, eliminarLista, listarListas } from '../../api/listasContratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function ContractorListsPage() {
  const [listas, setListas] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [modalAbierto, setModalAbierto] = useState(false);
  const [nombre, setNombre] = useState('');
  const [seleccionados, setSeleccionados] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null);

  const cargar = () =>
    Promise.all([listarListas(), listarContratistas()])
      .then(([listasData, contratistasData]) => {
        setListas(listasData);
        setContratistas(contratistasData);
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));

  useEffect(() => {
    cargar();
  }, []);

  const opcionesContratistas = contratistas.map((c) => ({
    value: String(c.id),
    label: `${c.nombre_empresa} (${c.especialidad})`,
  }));

  const handleCrear = async () => {
    if (nombre.trim().length < 2) {
      notifyError('El nombre de la lista debe tener al menos 2 caracteres.');
      return;
    }
    if (seleccionados.length === 0) {
      notifyError('Seleccioná al menos un contratista.');
      return;
    }
    setGuardando(true);
    try {
      await crearLista({ nombre, contratista_ids: seleccionados.map(Number) });
      notifySuccess('Lista creada correctamente.');
      setModalAbierto(false);
      setNombre('');
      setSeleccionados([]);
      setCargando(true);
      cargar();
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  const handleEliminar = async (listaId) => {
    setEliminandoId(listaId);
    try {
      await eliminarLista(listaId);
      setListas((actuales) => actuales.filter((l) => l.id !== listaId));
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="lg">
        <Title order={2}>Listas de contratistas</Title>
        <Button leftSection={<IconPlus size={18} />} onClick={() => setModalAbierto(true)}>
          Nueva lista
        </Button>
      </Group>

      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudieron cargar las listas">
          {errorCarga}
        </Alert>
      )}

      {!cargando && !errorCarga && listas.length === 0 && (
        <Paper withBorder radius="md" p="xl" style={{ borderStyle: 'dashed' }}>
          <Stack align="center" gap="xs" ta="center">
            <IconUsersGroup size={32} color="var(--mantine-color-dimmed)" />
            <Text fw={600}>Todavía no hay listas</Text>
            <Text size="sm" c="dimmed" maw={420}>
              Agrupá a los contratistas que convocás juntos (por ejemplo, los electricistas de una
              zona) y notificalos a todos de una vez al pedir presupuesto.
            </Text>
            <Button
              mt="xs"
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={() => setModalAbierto(true)}
            >
              Crear la primera lista
            </Button>
          </Stack>
        </Paper>
      )}

      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {listas.map((lista) => (
          <Card key={lista.id} withBorder radius="md">
            <Group justify="space-between" mb="xs">
              <Group gap="xs">
                <IconUsersGroup size={20} />
                <Text fw={600}>{lista.nombre}</Text>
                <Text size="sm" c="dimmed">
                  ({lista.contratistas.length} contratistas)
                </Text>
                {lista.contratistas.some((c) => c.fecha_baja) && (
                  <Text size="sm" c="dimmed">
                    · los dados de baja no se notifican
                  </Text>
                )}
              </Group>
              <ActionIcon
                color="red"
                variant="subtle"
                loading={eliminandoId === lista.id}
                onClick={() => handleEliminar(lista.id)}
                aria-label="Eliminar lista"
              >
                <IconTrash size={18} />
              </ActionIcon>
            </Group>
            <Text size="sm" c="dimmed">
              {lista.contratistas
                .map((c) =>
                  c.fecha_baja ? `${c.nombre_empresa} (dado de baja)` : c.nombre_empresa,
                )
                .join(', ')}
            </Text>
          </Card>
        ))}
      </SimpleGrid>

      <Modal
        opened={modalAbierto}
        onClose={() => setModalAbierto(false)}
        title="Nueva lista de contratistas"
        centered
      >
        <Stack>
          <TextInput
            label="Nombre de la lista"
            placeholder="Ej: Electricistas zona norte"
            value={nombre}
            onChange={(e) => setNombre(e.currentTarget.value)}
          />
          <MultiSelect
            label="Contratistas"
            placeholder="Elegí los contratistas"
            data={opcionesContratistas}
            value={seleccionados}
            onChange={setSeleccionados}
            searchable
            nothingFoundMessage="No hay contratistas"
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalAbierto(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCrear} loading={guardando}>
              Crear lista
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
