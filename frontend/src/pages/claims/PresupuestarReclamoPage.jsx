import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Autocomplete,
  Badge,
  Button,
  Card,
  Container,
  Divider,
  Group,
  Loader,
  NumberInput,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCircleCheck, IconMapPin } from '@tabler/icons-react';

import { API_URL } from '../../api/apiClient';
import { obtenerReclamo } from '../../api/reclamos';
import { obtenerMiFicha } from '../../api/contratistas';
import { crearPresupuesto } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';
import { PriorityBadge } from './PriorityBadge';

// Unidades sugeridas. Al ser Autocomplete, el contratista puede escribir cualquier otra.
const UNIDADES = ['kg', 'gramos', 'metros', 'metros²', 'metros³', 'litros', 'horas', 'cajas', 'rollos', 'bolsas'];

function esVideo(foto) {
  return foto.tipo === 'VIDEO' || /\.(mp4|mov|webm|3gp)$/i.test(foto.url);
}

function MediaGaleria({ fotos }) {
  if (!fotos || fotos.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        Este reclamo no tiene fotos ni videos adjuntos.
      </Text>
    );
  }

  return (
    <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm">
      {fotos.map((foto) => {
        const src = `${API_URL}${foto.url}`;
        return esVideo(foto) ? (
          <video
            key={foto.id}
            src={src}
            controls
            style={{ width: '100%', borderRadius: 8, aspectRatio: '1 / 1', objectFit: 'cover' }}
          />
        ) : (
          <a key={foto.id} href={src} target="_blank" rel="noreferrer">
            <img
              src={src}
              alt={foto.nombre_archivo}
              style={{ width: '100%', borderRadius: 8, aspectRatio: '1 / 1', objectFit: 'cover' }}
            />
          </a>
        );
      })}
    </SimpleGrid>
  );
}

export function PresupuestarReclamoPage() {
  const { id } = useParams();
  const reclamoId = Number(id);

  const [reclamo, setReclamo] = useState(null);
  const [miFicha, setMiFicha] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);

  const form = useForm({
    initialValues: {
      items: [{ description: '', quantity: '', unit: 'unidad', unitCost: '' }],
      notes: '',
    },
    validate: {
      items: {
        description: (v) => (v.trim() === '' ? 'Ingrese el material' : null),
        quantity: (v) => (v === '' || Number(v) <= 0 ? 'Debe ser mayor a 0' : null),
        unit: (v) => (!v || v.trim() === '' ? 'Ingrese la unidad' : null),
        unitCost: (v) => (v === '' || Number(v) < 0 ? 'No puede ser negativo' : null),
      },
    },
  });

  useEffect(() => {
    Promise.all([obtenerReclamo(reclamoId), obtenerMiFicha()])
      .then(([reclamoData, fichaData]) => {
        setReclamo(reclamoData);
        setMiFicha(fichaData);
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [reclamoId]);

  const total = form.values.items.reduce(
    (acc, item) => acc + (Number(item.quantity) || 0) * (Number(item.unitCost) || 0),
    0,
  );

  const handleSubmit = async (values) => {
    if (!miFicha?.id) {
      notifyError('No se pudo identificar tu ficha de contratista.');
      return;
    }

    setEnviando(true);
    try {
      await crearPresupuesto({
        reclamo_id: reclamoId,
        contratista_id: miFicha.id,
        observaciones: values.notes.trim() === '' ? null : values.notes,
        items: values.items.map((item) => ({
          descripcion: item.description,
          cantidad: item.quantity,
          unidad: item.unit || 'unidad',
          costo_unitario: item.unitCost,
        })),
      });
      form.reset();
      setEnviado(true);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  if (cargando) {
    return (
      <Container size="md" py="xl">
        <Loader />
      </Container>
    );
  }

  if (errorCarga || !reclamo) {
    return (
      <Container size="md" py="xl">
        <Alert color="red" title="No se pudo cargar el reclamo">
          {errorCarga || 'Reclamo no encontrado'}
        </Alert>
      </Container>
    );
  }

  if (enviado) {
    return (
      <Container size="sm" py={80}>
        <Stack align="center" gap="md">
          <IconCircleCheck size={72} color="var(--mantine-color-teal-6)" />
          <Title order={2} ta="center">
            ¡Gracias por cargar tu presupuesto!
          </Title>
          <Text ta="center" c="dimmed" size="lg">
            Tu presupuesto para el reclamo {formatearIdReclamo(reclamo.id)} quedó registrado y
            está pendiente de evaluación y aprobación. Muy pronto nos vamos a contactar con vos.
          </Text>
        </Stack>
      </Container>
    );
  }

  return (
    <Container size="md" py="xl">
      <Stack gap="lg">
        <div>
          <Group gap={8} mb={4}>
            <Text size="sm" c="dimmed" ff="monospace">
              {formatearIdReclamo(reclamo.id)}
            </Text>
            <PriorityBadge prioridad={reclamo.prioridad} size="xs" />
            <Badge variant="light">{reclamo.categoria}</Badge>
          </Group>
          <Title order={2}>{reclamo.nombre_escuela}</Title>
          <Group gap={4} c="dimmed" mt={4}>
            <IconMapPin size={15} />
            <Text size="sm">{reclamo.ubicacion}</Text>
          </Group>
        </div>

        <Card withBorder radius="md">
          <Text fw={600} mb="xs">
            Descripción del problema
          </Text>
          <Text size="sm">{reclamo.descripcion}</Text>
        </Card>

        <div>
          <Text fw={600} mb="sm">
            Fotos y videos
          </Text>
          <MediaGaleria fotos={reclamo.fotos} />
        </div>

        <Divider label="Cargar presupuesto" labelPosition="center" />

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <Text fw={500} size="sm">
              Ítems del presupuesto
            </Text>

            {form.values.items.map((_, index) => (
              <Group key={form.key(`items.${index}`)} align="flex-start" wrap="nowrap">
                <TextInput
                  placeholder="Material"
                  style={{ flex: 2 }}
                  key={form.key(`items.${index}.description`)}
                  {...form.getInputProps(`items.${index}.description`)}
                />
                <NumberInput
                  placeholder="Cantidad"
                  min={0}
                  decimalScale={2}
                  style={{ flex: 1 }}
                  key={form.key(`items.${index}.quantity`)}
                  {...form.getInputProps(`items.${index}.quantity`)}
                />
                <Autocomplete
                  placeholder="Unidad"
                  data={UNIDADES}
                  maxDropdownHeight={260}
                  comboboxProps={{ withinPortal: true }}
                  style={{ flex: 1 }}
                  key={form.key(`items.${index}.unit`)}
                  {...form.getInputProps(`items.${index}.unit`)}
                />
                <NumberInput
                  placeholder="Costo unitario"
                  min={0}
                  decimalScale={2}
                  prefix="$"
                  style={{ flex: 1 }}
                  key={form.key(`items.${index}.unitCost`)}
                  {...form.getInputProps(`items.${index}.unitCost`)}
                />
                <Button
                  type="button"
                  color="red"
                  variant="subtle"
                  disabled={form.values.items.length === 1}
                  onClick={() => form.removeListItem('items', index)}
                >
                  Quitar
                </Button>
              </Group>
            ))}

            <Button
              type="button"
              variant="light"
              onClick={() =>
                form.insertListItem('items', {
                  description: '',
                  quantity: '',
                  unit: 'unidad',
                  unitCost: '',
                })
              }
            >
              + Agregar ítem
            </Button>

            <Textarea
              label="Observaciones"
              placeholder="Notas adicionales (opcional)..."
              minRows={3}
              autosize
              key={form.key('notes')}
              {...form.getInputProps('notes')}
            />

            <Group justify="flex-end">
              <Text fw={700} size="lg">
                Total: {formatoMoneda.format(total)}
              </Text>
            </Group>

            <Button type="submit" mt="sm" loading={enviando}>
              Enviar presupuesto
            </Button>
          </Stack>
        </form>
      </Stack>
    </Container>
  );
}
