import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
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
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconChecks,
  IconClipboardList,
  IconHistory,
  IconMapPin,
  IconPhoto,
  IconReceipt2,
  IconTruck,
} from '@tabler/icons-react';

import { obtenerHistorialReclamo, obtenerReclamo, obtenerVisitaReclamo } from '../../api/reclamos';
import { formatearIdReclamo } from '../../utils/ids';
import { esAdministrador } from '../../utils/auth';
import { notifyError } from '../../utils/notifications';
import { BudgetRequestsList } from './BudgetRequestsList';
import { ClaimPhotosManager } from './ClaimPhotosManager';
import { NotifyContractorsModal } from './NotifyContractorsModal';
import { PriorityBadge } from './PriorityBadge';
import { StatusBadge } from './StatusBadge';
import { colorPorEstado, etiquetaPorEstado, proximoPasoPorEstado } from './estados';

const iconoPorEstado = {
  PENDIENTE_REVISION: IconClipboardList,
  PENDIENTE_PRESUPUESTO: IconReceipt2,
  EN_EVALUACION: IconReceipt2,
  APROBADO: IconChecks,
  PENDIENTE_COORDINACION: IconCalendarEvent,
  VISITA_COORDINADA: IconCalendarEvent,
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

export function ClaimDetailDrawer({ reclamoId, onClose }) {
  // Guarda el último fetch resuelto junto con el id al que corresponde: así `cargando`
  // se puede derivar comparando contra `reclamoId` en vez de duplicar estado, y una
  // respuesta vieja que llega tarde (ej. al cambiar rápido de reclamo) no pisa una más nueva.
  const [ultimoCargado, setUltimoCargado] = useState({
    id: null,
    reclamo: null,
    historial: [],
    visita: null,
  });

  useEffect(() => {
    if (reclamoId === null) return;
    let vigente = true;
    Promise.all([
      obtenerReclamo(reclamoId),
      obtenerHistorialReclamo(reclamoId),
      obtenerVisitaReclamo(reclamoId),
    ])
      .then(([reclamo, historial, visita]) => {
        if (vigente) setUltimoCargado({ id: reclamoId, reclamo, historial, visita });
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      });
    return () => {
      vigente = false;
    };
  }, [reclamoId]);

  const [notificarAbierto, setNotificarAbierto] = useState(false);

  const cargadoCoincide = ultimoCargado.id === reclamoId;
  const reclamo = cargadoCoincide ? ultimoCargado.reclamo : null;
  const historial = cargadoCoincide ? ultimoCargado.historial : [];
  const visita = cargadoCoincide ? ultimoCargado.visita : null;
  const cargando = reclamoId !== null && reclamo === null;

  const proximoPaso = reclamo ? proximoPasoPorEstado[reclamo.estado] : null;
  const esAdmin = esAdministrador();
  const puedeNotificar = esAdmin && reclamo?.estado === 'PENDIENTE_PRESUPUESTO';
  // Una vez solicitado el presupuesto, el reclamo deja PENDIENTE_REVISION. A partir
  // de ahí tiene sentido ver a quién se le pidió y quién ya respondió.
  const mostrarSolicitudes =
    esAdmin && reclamo && reclamo.estado !== 'PENDIENTE_REVISION';

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
          {reclamo.telefono_creador && (
            <Group gap={6} mb="md" c="dimmed">
              <IconBrandWhatsapp size={15} color="var(--mantine-color-teal-6)" />
              <Text size="sm">
                Creado desde WhatsApp por{' '}
                <Text span fw={600} c="dark">
                  {reclamo.telefono_creador}
                </Text>
              </Text>
            </Group>
          )}

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

          {visita && visita.estado === 'CONFIRMADA' && visita.horario_confirmado && (
            <Paper
              radius="md"
              p="sm"
              mb="md"
              style={{
                backgroundColor: 'var(--mantine-color-green-0)',
                borderLeft: '4px solid var(--mantine-color-green-6)',
              }}
            >
              <Group gap="xs" mb={4} wrap="nowrap">
                <ThemeIcon size={24} radius="xl" variant="filled" color="green">
                  <IconCalendarEvent size={14} />
                </ThemeIcon>
                <Text fw={700} size="sm" c="green.9">
                  Visita de trabajo coordinada
                </Text>
              </Group>
              <Text fw={600} size="sm" ml={32}>
                {visita.horario_confirmado}
              </Text>
            </Paper>
          )}

          {visita && visita.estado === 'ESPERANDO_DISPONIBILIDAD' && (
            <Text size="sm" c="dimmed" mb="md" ml={2}>
              🕓 Esperando que el contratista proponga horarios para la visita.
            </Text>
          )}

          {visita && visita.estado === 'ESPERANDO_ELECCION' && (
            <Text size="sm" c="dimmed" mb="md" ml={2}>
              🕓 Esperando que el responsable del reclamo elija un horario para la visita.
            </Text>
          )}

          {puedeNotificar && (
            <Button
              fullWidth
              mb="md"
              color="teal"
              leftSection={<IconBrandWhatsapp size={18} />}
              onClick={() => setNotificarAbierto(true)}
            >
              Notificar contratistas para presupuestar
            </Button>
          )}

          <Paper withBorder radius="md" p="md" mb="md">
            <Group gap={8} mb={6}>
              <IconClipboardList size={16} color="var(--mantine-color-dimmed)" />
              <Text fw={600} size="sm">
                Descripción del problema
              </Text>
            </Group>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {reclamo.descripcion}
            </Text>

            {reclamo.observaciones && (
              <>
                <Text fw={600} size="sm" mt="md" mb={4}>
                  Información adicional
                </Text>
                <Text size="sm" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
                  {reclamo.observaciones}
                </Text>
              </>
            )}
          </Paper>

          <Tabs defaultValue="avance">
            <Tabs.List>
              <Tabs.Tab value="avance" leftSection={<IconHistory size={16} />}>
                Avance
              </Tabs.Tab>
              <Tabs.Tab value="fotos" leftSection={<IconPhoto size={16} />}>
                Fotos
              </Tabs.Tab>
              {mostrarSolicitudes && (
                <Tabs.Tab value="presupuestos" leftSection={<IconReceipt2 size={16} />}>
                  Presupuestos
                </Tabs.Tab>
              )}
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
              <ClaimPhotosManager
                reclamoId={reclamo.id}
                fotosIniciales={reclamo.fotos}
                soloLectura
              />
            </Tabs.Panel>

            {mostrarSolicitudes && (
              <Tabs.Panel value="presupuestos" pt="md">
                <BudgetRequestsList reclamoId={reclamo.id} />
              </Tabs.Panel>
            )}
          </Tabs>

          {puedeNotificar && (
            <NotifyContractorsModal
              reclamoId={reclamo.id}
              opened={notificarAbierto}
              onClose={() => setNotificarAbierto(false)}
            />
          )}
        </>
      )}
    </Drawer>
  );
}
