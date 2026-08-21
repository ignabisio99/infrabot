import { useEffect, useState } from 'react';
import {
  Badge,
  Drawer,
  Group,
  Loader,
  Paper,
  Tabs,
  Text,
  ThemeIcon,
  Timeline,
} from '@mantine/core';
import {
  IconArrowRight,
  IconBan,
  IconBolt,
  IconChecks,
  IconClipboardList,
  IconHistory,
  IconMapPin,
  IconPhoto,
  IconReceipt2,
  IconSparkles,
  IconTruck,
} from '@tabler/icons-react';

import { obtenerHistorialReclamo, obtenerReclamo } from '../../api/reclamos';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError } from '../../utils/notifications';
import { ClaimIAPanel } from './ClaimIAPanel';
import { ClaimPhotosManager } from './ClaimPhotosManager';
import { PriorityBadge } from './PriorityBadge';
import { StatusBadge } from './StatusBadge';
import { colorPorEstado, etiquetaPorEstado, proximoPasoPorEstado } from './estados';

const iconoPorEstado = {
  PENDIENTE_REVISION: IconClipboardList,
  PENDIENTE_PRESUPUESTO: IconReceipt2,
  EN_EVALUACION: IconReceipt2,
  APROBADO: IconChecks,
  EN_EJECUCION: IconTruck,
  FINALIZADO: IconChecks,
  DESIERTO: IconBan,
  RECHAZADO: IconBan,
  CANCELADO: IconBan,
};

function tituloEvento(evento) {
  if (evento.estado_anterior === null) return 'Reclamo creado';
  return `Pasó a "${etiquetaPorEstado[evento.estado_nuevo]}"`;
}

// TODO: cuando existan roles, mostrar el nombre del usuario en los cambios MANUAL.
function TituloEvento({ evento }) {
  return (
    <Group gap={6} wrap="nowrap">
      <Text size="sm" fw={500}>
        {tituloEvento(evento)}
      </Text>
      {evento.origen === 'AUTOMATICO' && (
        <Badge
          size="xs"
          variant="light"
          color="grape"
          leftSection={<IconBolt size={10} />}
          tt="none"
        >
          Automático
        </Badge>
      )}
    </Group>
  );
}

export function ClaimDetailDrawer({ reclamoId, onClose, onAbrirReclamo, onReclamoActualizado }) {
  // Guarda el último fetch resuelto junto con el id al que corresponde: así `cargando`
  // se puede derivar comparando contra `reclamoId` en vez de duplicar estado, y una
  // respuesta vieja que llega tarde (ej. al cambiar rápido de reclamo) no pisa una más nueva.
  const [ultimoCargado, setUltimoCargado] = useState({ id: null, reclamo: null, historial: [] });
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    if (reclamoId === null) return;
    let vigente = true;
    Promise.all([obtenerReclamo(reclamoId), obtenerHistorialReclamo(reclamoId)])
      .then(([reclamo, historial]) => {
        if (vigente) setUltimoCargado({ id: reclamoId, reclamo, historial });
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      });
    return () => {
      vigente = false;
    };
  }, [reclamoId, recarga]);

  const cargadoCoincide = ultimoCargado.id === reclamoId;
  const reclamo = cargadoCoincide ? ultimoCargado.reclamo : null;
  const historial = cargadoCoincide ? ultimoCargado.historial : [];
  const cargando = reclamoId !== null && reclamo === null;

  const proximoPaso = reclamo ? proximoPasoPorEstado[reclamo.estado] : null;

  return (
    <Drawer
      opened={reclamoId !== null}
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
                <PriorityBadge prioridad={reclamo.prioridad} size="xs" />
                <StatusBadge estado={reclamo.estado} size="xs" variant="light" />
                {reclamo.requiere_revision && (
                  <Badge size="xs" color="orange" variant="light" tt="none">
                    Revisión
                  </Badge>
                )}
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
      {cargando && <Loader />}

      {!cargando && reclamo && (
        <>
          {proximoPaso && (
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
                {proximoPaso.titulo}
              </Text>
              <Text size="sm" c="dimmed" ml={32}>
                {proximoPaso.descripcion}
              </Text>
            </Paper>
          )}

          <Text size="sm" mb={4}>
            <Text span fw={600}>
              Categoría:{' '}
            </Text>
            {reclamo.categoria}
          </Text>
          <Text size="sm" mb="xs">
            {reclamo.descripcion}
          </Text>
          {reclamo.observaciones && (
            <Text size="sm" c="dimmed" mb="md">
              {reclamo.observaciones}
            </Text>
          )}

          <Tabs defaultValue="avance">
            <Tabs.List>
              <Tabs.Tab value="avance" leftSection={<IconHistory size={16} />}>
                Avance
              </Tabs.Tab>
              <Tabs.Tab value="fotos" leftSection={<IconPhoto size={16} />}>
                Fotos
              </Tabs.Tab>
              <Tabs.Tab value="ia" leftSection={<IconSparkles size={16} />}>
                IA
              </Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="avance" pt="md">
              {historial.length === 0 ? (
                <Text c="dimmed" size="sm">
                  Todavía no hay movimientos registrados.
                </Text>
              ) : (
                <Timeline active={historial.length} bulletSize={24} lineWidth={2}>
                  {historial.map((evento) => {
                    const Icono = iconoPorEstado[evento.estado_nuevo] ?? IconClipboardList;
                    return (
                      <Timeline.Item
                        key={evento.id}
                        title={<TituloEvento evento={evento} />}
                        bullet={<Icono size={14} />}
                        color={colorPorEstado[evento.estado_nuevo]}
                      >
                        {evento.motivo && (
                          <Text size="sm" c="dimmed">
                            {evento.motivo}
                          </Text>
                        )}
                        <Text size="xs" c="dimmed" mt={4}>
                          {new Date(evento.fecha).toLocaleString('es-AR')}
                        </Text>
                      </Timeline.Item>
                    );
                  })}
                </Timeline>
              )}
            </Tabs.Panel>

            <Tabs.Panel value="fotos" pt="md">
              <ClaimPhotosManager reclamoId={reclamo.id} fotosIniciales={reclamo.fotos} />
            </Tabs.Panel>

            <Tabs.Panel value="ia" pt="md">
              <ClaimIAPanel
                reclamo={reclamo}
                onAbrirReclamo={onAbrirReclamo}
                onReclamoActualizado={() => {
                  setRecarga((n) => n + 1);
                  onReclamoActualizado?.();
                }}
              />
            </Tabs.Panel>
          </Tabs>
        </>
      )}
    </Drawer>
  );
}
