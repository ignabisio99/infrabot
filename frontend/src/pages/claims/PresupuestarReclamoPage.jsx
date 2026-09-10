import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Badge,
  Button,
  Card,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCircleCheck, IconInfoCircle, IconMapPin } from '@tabler/icons-react';

import { API_URL } from '../../api/apiClient';
import { obtenerReclamo } from '../../api/reclamos';
import { obtenerMiFicha, solicitarInformacionReclamo } from '../../api/contratistas';
import { crearPresupuesto } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError, notifySuccess } from '../../utils/notifications';
import {
  LABOR_VACIA,
  MATERIAL_VACIO,
  serializarItems,
  totalLineas,
  validarLineasPresupuesto,
} from '../../utils/presupuestoItems';
import { BudgetLineItems } from '../budgets/BudgetLineItems';
import { PriorityBadge } from './PriorityBadge';

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

  const [infoModalAbierto, setInfoModalAbierto] = useState(false);
  const [mensajeInfo, setMensajeInfo] = useState('');
  const [enviandoInfo, setEnviandoInfo] = useState(false);

  const form = useForm({
    initialValues: {
      materials: [{ ...MATERIAL_VACIO }],
      labor: [{ ...LABOR_VACIA }],
      notes: '',
    },
    validate: (values) => validarLineasPresupuesto(values.materials, values.labor),
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

  const total = totalLineas(form.values.materials, form.values.labor);

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
        items: serializarItems(values.materials, values.labor),
      });
      form.reset();
      setEnviado(true);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  const handleSolicitarInfo = async () => {
    if (mensajeInfo.trim().length < 5) {
      notifyError('Escribí un mensaje con lo que necesitás (mínimo 5 caracteres).');
      return;
    }
    setEnviandoInfo(true);
    try {
      await solicitarInformacionReclamo(reclamoId, mensajeInfo.trim());
      notifySuccess('Tu solicitud de información fue enviada a quien creó el reclamo.');
      setInfoModalAbierto(false);
      setMensajeInfo('');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviandoInfo(false);
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

        {reclamo.telefono_creador && (
          <Card withBorder radius="md" bg="var(--mantine-color-orange-0)">
            <Group justify="space-between" wrap="nowrap" gap="md">
              <div>
                <Text fw={600} size="sm">
                  ¿La información del reclamo no es suficiente?
                </Text>
                <Text size="sm" c="dimmed">
                  Pedile más detalles a quien lo creó antes de cargar tu presupuesto.
                </Text>
              </div>
              <Button
                variant="light"
                color="orange"
                leftSection={<IconInfoCircle size={18} />}
                onClick={() => setInfoModalAbierto(true)}
                style={{ flexShrink: 0 }}
              >
                Necesito más información
              </Button>
            </Group>
          </Card>
        )}

        <Divider label="Cargar presupuesto" labelPosition="center" />

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <Textarea
              label="Detalle de la tarea a realizar"
              placeholder="Describí el trabajo que cubre este presupuesto..."
              minRows={3}
              autosize
              key={form.key('notes')}
              {...form.getInputProps('notes')}
            />

            <BudgetLineItems form={form} />

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

      <Modal
        opened={infoModalAbierto}
        onClose={() => setInfoModalAbierto(false)}
        title="Solicitar más información"
        centered
      >
        <Stack>
          <Text size="sm" c="dimmed">
            Contanos qué información necesitás para poder cargar el presupuesto. El mensaje se
            le va a enviar por WhatsApp a la persona que creó el reclamo.
          </Text>
          <Textarea
            placeholder="Ej: ¿Podrían enviar fotos del tablero desde otro ángulo? ¿Cuáles son las medidas del espacio?"
            minRows={4}
            autosize
            value={mensajeInfo}
            onChange={(e) => setMensajeInfo(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setInfoModalAbierto(false)}>
              Cancelar
            </Button>
            <Button color="orange" onClick={handleSolicitarInfo} loading={enviandoInfo}>
              Enviar solicitud
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
