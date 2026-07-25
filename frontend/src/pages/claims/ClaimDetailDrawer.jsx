import { useState } from 'react';
import {
  Badge,
  Drawer,
  Group,
  Image,
  Modal,
  Paper,
  SimpleGrid,
  Tabs,
  Text,
  ThemeIcon,
  Timeline,
  UnstyledButton,
} from '@mantine/core';
import {
  IconArrowRight,
  IconBulb,
  IconClipboardList,
  IconHistory,
  IconMapPin,
  IconPhoto,
  IconReceipt2,
  IconTruck,
} from '@tabler/icons-react';

import { formatearIdReclamo } from '../../utils/ids';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

// TODO: reemplazar por fotos reales cuando el backend exponga un endpoint de adjuntos
const FOTOS_MOCK = [
  { id: 1, etiqueta: 'Foto 1', url: 'https://picsum.photos/seed/reclamo-1/600/600' },
  { id: 2, etiqueta: 'Foto 2', url: 'https://picsum.photos/seed/reclamo-2/600/600' },
  { id: 3, etiqueta: 'Foto 3', url: 'https://picsum.photos/seed/reclamo-3/600/600' },
  { id: 4, etiqueta: 'Foto 4', url: 'https://picsum.photos/seed/reclamo-4/600/600' },
];

// Suma `dias` a la fecha de creación del reclamo, para que cada evento del
// historial mockeado quede en una fecha posterior al anterior.
function fechaMock(reclamo, dias) {
  if (!reclamo?.fecha_creacion) return null;
  const fecha = new Date(reclamo.fecha_creacion);
  fecha.setDate(fecha.getDate() + dias);
  return fecha;
}

// TODO: reemplazar por la acción sugerida real cuando el backend la calcule
const PROXIMA_ACCION_MOCK = {
  titulo: 'Coordinación de trabajo',
  descripcion: 'Coordinar con Constructora Del Sur S.A. la fecha de inicio de la obra.',
};

// TODO: reemplazar por historial real cuando el backend registre eventos de tracking
function historialMock(reclamo) {
  return [
    {
      id: 1,
      tipo: 'creacion',
      titulo: 'Reclamo creado',
      descripcion: `Se cargó el reclamo para ${reclamo?.nombre_escuela ?? 'la escuela'}.`,
      fecha: fechaMock(reclamo, 0),
    },
    {
      id: 2,
      tipo: 'ia',
      titulo: 'Presupuesto preliminar con IA',
      descripcion: 'El sistema generó un presupuesto preliminar estimado para este reclamo.',
      fecha: fechaMock(reclamo, 1),
    },
    {
      id: 3,
      tipo: 'presupuesto',
      titulo: 'Presupuesto cargado',
      descripcion: 'Constructora Del Sur S.A. cargó un presupuesto para este reclamo.',
      fecha: fechaMock(reclamo, 3),
    },
    {
      id: 4,
      tipo: 'presupuesto',
      titulo: 'Presupuesto cargado',
      descripcion: 'Herrera Obras Viales cargó un presupuesto para este reclamo.',
      fecha: fechaMock(reclamo, 4),
    },
    {
      id: 5,
      tipo: 'contratista',
      titulo: 'Contratista elegido',
      descripcion: 'Se seleccionó a Constructora Del Sur S.A. para realizar el trabajo.',
      fecha: fechaMock(reclamo, 5),
    },
  ];
}

const iconoPorTipo = {
  creacion: IconClipboardList,
  ia: IconBulb,
  presupuesto: IconReceipt2,
  contratista: IconTruck,
};

const colorPorTipo = {
  creacion: 'gray',
  ia: 'grape',
  presupuesto: 'blue',
  contratista: '#1fa7b3',
};

function FotoConEtiqueta({ foto }) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Image src={foto.url} alt={foto.etiqueta} radius="md" h="100%" w="100%" fit="cover" />
      <Text
        size="xs"
        c="white"
        fw={500}
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '6px 8px',
          borderBottomLeftRadius: 8,
          borderBottomRightRadius: 8,
          background: 'linear-gradient(to top, rgba(0,0,0,0.65), transparent)',
        }}
      >
        {foto.etiqueta}
      </Text>
    </div>
  );
}

export function ClaimDetailDrawer({ reclamo, onClose }) {
  const [fotoAmpliada, setFotoAmpliada] = useState(null);

  return (
    <>
      <Drawer
        opened={reclamo !== null}
        onClose={onClose}
        position="right"
        size="lg"
        title={
          reclamo && (
            <Group gap="sm" wrap="nowrap" py={2}>
              <ThemeIcon size={40} radius="md" variant="light" color="#1fa7b3">
                <IconClipboardList size={20} />
              </ThemeIcon>
              <div>
                <Group gap={8} mb={2}>
                  <Text size="xs" c="dimmed" ff="monospace">
                    {formatearIdReclamo(reclamo.id)}
                  </Text>
                  <Badge size="xs" color={colorPorPrioridad[reclamo.prioridad]}>
                    {reclamo.prioridad}
                  </Badge>
                </Group>
                <Text fw={700} size="lg" lh={1.15}>
                  {reclamo.nombre_escuela}
                </Text>
                <Group gap={4} c="dimmed">
                  <IconMapPin size={13} />
                  <Text size="xs">{reclamo.ubicacion}</Text>
                </Group>
              </div>
            </Group>
          )
        }
        styles={{
          header: { borderBottom: '1px solid var(--mantine-color-gray-3)', paddingBottom: 12 },
          body: { paddingTop: 16 },
        }}
      >
        {reclamo && (
          <>
            <Paper
              radius="md"
              p="sm"
              mb="md"
              style={{
                backgroundColor: 'var(--mantine-color-teal-0)',
                borderLeft: '4px solid #1fa7b3',
              }}
            >
              <Group gap="xs" mb={4} wrap="nowrap">
                <ThemeIcon size={24} radius="xl" variant="filled" color="teal">
                  <IconArrowRight size={14} />
                </ThemeIcon>
                <Text fw={700} size="sm" c="teal.9">
                  Próximo paso
                </Text>
              </Group>
              <Text fw={600} size="sm" ml={32}>
                {PROXIMA_ACCION_MOCK.titulo}
              </Text>
              <Text size="sm" c="dimmed" ml={32}>
                {PROXIMA_ACCION_MOCK.descripcion}
              </Text>
            </Paper>

            <Tabs defaultValue="avance">
              <Tabs.List>
                <Tabs.Tab value="avance" leftSection={<IconHistory size={16} />}>
                  Avance
                </Tabs.Tab>
                <Tabs.Tab value="fotos" leftSection={<IconPhoto size={16} />}>
                  Fotos
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="avance" pt="md">
                <Timeline active={historialMock(reclamo).length} bulletSize={24} lineWidth={2}>
                  {historialMock(reclamo).map((evento) => {
                    const Icono = iconoPorTipo[evento.tipo];
                    return (
                      <Timeline.Item
                        key={evento.id}
                        title={evento.titulo}
                        bullet={<Icono size={14} />}
                        color={colorPorTipo[evento.tipo]}
                      >
                        <Text size="sm" c="dimmed">
                          {evento.descripcion}
                        </Text>
                        {evento.fecha && (
                          <Text size="xs" c="dimmed" mt={4}>
                            {new Date(evento.fecha).toLocaleString('es-AR')}
                          </Text>
                        )}
                      </Timeline.Item>
                    );
                  })}
                </Timeline>
              </Tabs.Panel>

              <Tabs.Panel value="fotos" pt="md">
                <SimpleGrid cols={3} spacing="sm">
                  {FOTOS_MOCK.map((foto) => (
                    <UnstyledButton
                      key={foto.id}
                      onClick={() => setFotoAmpliada(foto)}
                      style={{ aspectRatio: '1 / 1' }}
                    >
                      <FotoConEtiqueta foto={foto} />
                    </UnstyledButton>
                  ))}
                </SimpleGrid>
              </Tabs.Panel>
            </Tabs>
          </>
        )}
      </Drawer>

      <Modal
        opened={fotoAmpliada !== null}
        onClose={() => setFotoAmpliada(null)}
        title={fotoAmpliada?.etiqueta}
        size="lg"
      >
        <div style={{ aspectRatio: '16 / 10' }}>
          <Image
            src={fotoAmpliada?.url}
            alt={fotoAmpliada?.etiqueta}
            radius="md"
            h="100%"
            w="100%"
            fit="cover"
          />
        </div>
      </Modal>
    </>
  );
}
