import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Drawer,
  Group,
  Loader,
  Modal,
  Paper,
  Radio,
  Stack,
  Tabs,
  Text,
  ThemeIcon,
  Timeline,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArrowRight,
  IconBan,
  IconBolt,
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconChecks,
  IconClipboardList,
  IconHistory,
  IconInfoCircle,
  IconMapPin,
  IconEyeCheck,
  IconPhoto,
  IconReceipt2,
  IconSparkles,
  IconTruck,
  IconArrowsExchange,
} from '@tabler/icons-react';

import {
  listarComentariosReclamo,
  obtenerHistorialReclamo,
  obtenerReclamo,
  obtenerVisitaReclamo,
  asignarOfertaExistente,
  cambiarEstadoReclamo,
  listarOfertasReutilizables,
  reabrirConvocatoria,
} from '../../api/reclamos';
import { formatoMoneda } from '../../utils/formatters';
import { avisarNotificacionesCambiaron } from '../../layout/NotificationBell';
import { formatearIdReclamo } from '../../utils/ids';
import { esAdministrador, esInspector } from '../../utils/auth';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { BudgetRequestsList } from './BudgetRequestsList';
import { ChangeStatusModal } from './ChangeStatusModal';
import { ClaimCommentsThread } from './ClaimComments';
import { ClaimIAPanel } from './ClaimIAPanel';
import { ClaimPhotosManager } from './ClaimPhotosManager';
import { NotifyContractorsModal } from './NotifyContractorsModal';
import { PriorityBadge } from './PriorityBadge';
import { StatusBadge } from './StatusBadge';
import {
  colorPorEstado,
  estadosFinales,
  etiquetaPorEstado,
  proximoPasoPorEstado,
} from './estados';

const iconoPorEstado = {
  PENDIENTE_REVISION: IconClipboardList,
  PENDIENTE_PRESUPUESTO: IconReceipt2,
  EN_EVALUACION: IconReceipt2,
  APROBADO: IconChecks,
  PENDIENTE_COORDINACION: IconCalendarEvent,
  VISITA_COORDINADA: IconCalendarEvent,
  EN_EJECUCION: IconTruck,
  PENDIENTE_INTERVENCION: IconAlertTriangle,
  FINALIZADO: IconChecks,
  DESIERTO: IconBan,
  RECHAZADO: IconBan,
  CANCELADO: IconBan,
};

const AYUDA_INSPECTOR =
  'Lo que escribas acá lo ven el administrador y los contratistas al presupuestar. No se puede editar ni borrar.';
const AYUDA_COMENTARIOS =
  'Observaciones de los inspectores. Los contratistas también las ven al cargar su presupuesto.';

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
  const [ultimoCargado, setUltimoCargado] = useState({
    id: null,
    reclamo: null,
    historial: [],
    visita: null,
    comentarios: [],
  });
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    if (reclamoId === null) return;
    let vigente = true;
    Promise.all([
      obtenerReclamo(reclamoId),
      obtenerHistorialReclamo(reclamoId),
      obtenerVisitaReclamo(reclamoId),
      listarComentariosReclamo(reclamoId),
    ])
      .then(([reclamo, historial, visita, comentarios]) => {
        if (vigente) setUltimoCargado({ id: reclamoId, reclamo, historial, visita, comentarios });
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      });
    return () => {
      vigente = false;
    };
  }, [reclamoId, recarga]);

  const [notificarAbierto, setNotificarAbierto] = useState(false);
  const [cambiarEstadoAbierto, setCambiarEstadoAbierto] = useState(false);
  const [confirmarReabrir, setConfirmarReabrir] = useState(false);
  const [reabriendo, setReabriendo] = useState(false);
  const [asignandoOferta, setAsignandoOferta] = useState(false);
  const [volviendoEjecucion, setVolviendoEjecucion] = useState(false);
  const [ofertasReutilizables, setOfertasReutilizables] = useState([]);
  const [cargandoOfertas, setCargandoOfertas] = useState(false);
  const [ofertaElegida, setOfertaElegida] = useState(null);

  const cargadoCoincide = ultimoCargado.id === reclamoId;
  const reclamo = cargadoCoincide ? ultimoCargado.reclamo : null;
  const historial = cargadoCoincide ? ultimoCargado.historial : [];
  const visita = cargadoCoincide ? ultimoCargado.visita : null;
  const comentarios = cargadoCoincide ? ultimoCargado.comentarios : [];
  const cargando = reclamoId !== null && reclamo === null;

  const proximoPaso = reclamo ? proximoPasoPorEstado[reclamo.estado] : null;
  const esAdmin = esAdministrador();
  const inspector = esInspector();
  const puedeCambiarEstado = esAdmin && (reclamo?.estados_posibles?.length ?? 0) > 0;
  const puedeNotificar = esAdmin && reclamo?.estado === 'PENDIENTE_PRESUPUESTO';
  const pendienteIntervencion = reclamo?.estado === 'PENDIENTE_INTERVENCION';

  const volverAEjecucion = async () => {
    setVolviendoEjecucion(true);
    try {
      await cambiarEstadoReclamo(
        reclamo.id,
        'EN_EJECUCION',
        'El administrador confirmó que el contratista sigue en obra',
      );
      notifySuccess('El reclamo volvió a ejecución.');
      setRecarga((n) => n + 1);
      onReclamoActualizado?.();
      avisarNotificacionesCambiaron();
    } catch (err) {
      notifyError(err.message);
    } finally {
      setVolviendoEjecucion(false);
    }
  };

  useEffect(() => {
    if (!confirmarReabrir || !reclamo?.id) return;
    setCargandoOfertas(true);
    setOfertaElegida(null);
    listarOfertasReutilizables(reclamo.id)
      .then(setOfertasReutilizables)
      .catch((err) => {
        notifyError(err.message);
        setOfertasReutilizables([]);
      })
      .finally(() => setCargandoOfertas(false));
  }, [confirmarReabrir, reclamo?.id]);

  const cancelarPresupuestoYConvocar = async () => {
    setReabriendo(true);
    try {
      await reabrirConvocatoria(reclamo.id);
      notifySuccess(
        'Se canceló el presupuesto. Avisamos a la escuela y al contratista: el reclamo volvió a presupuestos.',
      );
      setConfirmarReabrir(false);
      setRecarga((n) => n + 1);
      onReclamoActualizado?.();
      avisarNotificacionesCambiaron();
      setNotificarAbierto(true);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setReabriendo(false);
    }
  };

  const elegirOfertaExistente = async () => {
    if (!ofertaElegida) return;
    setAsignandoOferta(true);
    try {
      await asignarOfertaExistente(reclamo.id, Number(ofertaElegida));
      notifySuccess(
        'Se asignó otra oferta ya enviada. Avisamos a la escuela y se coordina una nueva visita.',
      );
      setConfirmarReabrir(false);
      setRecarga((n) => n + 1);
      onReclamoActualizado?.();
      avisarNotificacionesCambiaron();
    } catch (err) {
      notifyError(err.message);
    } finally {
      setAsignandoOferta(false);
    }
  };
  // Una vez solicitado el presupuesto, el reclamo deja PENDIENTE_REVISION. A partir
  // de ahí tiene sentido ver a quién se le pidió y quién ya respondió.
  const mostrarSolicitudes = esAdmin && reclamo && reclamo.estado !== 'PENDIENTE_REVISION';
  const visitaYaCoordinada =
    visita?.estado === 'CONFIRMADA' ||
    ['VISITA_COORDINADA', 'EN_EJECUCION', 'PENDIENTE_INTERVENCION', 'FINALIZADO'].includes(
      reclamo?.estado,
    );

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

          {pendienteIntervencion && (
            <Alert
              color="orange"
              variant="light"
              icon={<IconAlertTriangle size={18} />}
              mb="md"
              title="Pendiente de intervención"
            >
              <Text size="sm" mb={esAdmin ? 'sm' : 0}>
                El contratista no respondió los recordatorios de avance. Si hablaste con él y
                sigue en obra, volvé a ejecución. Si no, podés elegir otra oferta que ya se
                había enviado o convocar a otros contratistas.
              </Text>
              {esAdmin && (
                <Group gap="sm">
                  <Button
                    variant="light"
                    color="indigo"
                    loading={volviendoEjecucion}
                    onClick={volverAEjecucion}
                  >
                    Volver a ejecución
                  </Button>
                  <Button color="orange" onClick={() => setConfirmarReabrir(true)}>
                    Cambiar contratista
                  </Button>
                </Group>
              )}
            </Alert>
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

          {visita && visita.estado === 'ESPERANDO_DISPONIBILIDAD' && !visitaYaCoordinada && (
            <Text size="sm" c="dimmed" mb="md" ml={2}>
              🕓 Esperando que el contratista proponga horarios para la visita.
            </Text>
          )}

          {visita && visita.estado === 'ESPERANDO_ELECCION' && !visitaYaCoordinada && (
            <Text size="sm" c="dimmed" mb="md" ml={2}>
              🕓 Esperando que el responsable del reclamo elija un horario para la visita.
            </Text>
          )}

          {puedeCambiarEstado && (
            <Button
              fullWidth
              mb="md"
              variant="light"
              color="#1fa7b3"
              leftSection={<IconArrowsExchange size={18} />}
              onClick={() => setCambiarEstadoAbierto(true)}
            >
              Cambiar estado del reclamo
            </Button>
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
              <Tabs.Tab
                value="comentarios"
                leftSection={<IconEyeCheck size={16} />}
                rightSection={
                  <Badge size="xs" variant="light" color={comentarios.length > 0 ? 'teal' : 'gray'}>
                    {comentarios.length}
                  </Badge>
                }
              >
                Inspección
              </Tabs.Tab>
              {!inspector && (
                <Tabs.Tab value="ia" leftSection={<IconSparkles size={16} />}>
                  IA
                </Tabs.Tab>
              )}
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

            <Tabs.Panel value="comentarios" pt="md">
              <Group gap={6} mb="sm" wrap="nowrap" align="flex-start" c="dimmed">
                <IconInfoCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                <Text size="sm">{inspector ? AYUDA_INSPECTOR : AYUDA_COMENTARIOS}</Text>
              </Group>
              <ClaimCommentsThread
                reclamoId={reclamo.id}
                comentarios={comentarios}
                puedeComentar={inspector && !estadosFinales.includes(reclamo.estado)}
                onComentarioAgregado={(nuevo) =>
                  setUltimoCargado((actual) =>
                    actual.id === nuevo.reclamo_id
                      ? { ...actual, comentarios: [...actual.comentarios, nuevo] }
                      : actual,
                  )
                }
              />
            </Tabs.Panel>

            {!inspector && (
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
            )}

            {mostrarSolicitudes && (
              <Tabs.Panel value="presupuestos" pt="md">
                <BudgetRequestsList reclamoId={reclamo.id} />
              </Tabs.Panel>
            )}
          </Tabs>

          {esAdmin && (
            <NotifyContractorsModal
              reclamoId={reclamo.id}
              opened={notificarAbierto}
              onClose={() => setNotificarAbierto(false)}
            />
          )}

          <Modal
            opened={confirmarReabrir}
            onClose={() => setConfirmarReabrir(false)}
            title="Cambiar contratista"
            centered
          >
            <Stack gap="md">
              {cargandoOfertas && <Loader size="sm" />}
              {!cargandoOfertas && ofertasReutilizables.length > 0 && (
                <>
                  <Text size="sm">
                    Hay ofertas que ya se habían enviado y no se eligieron. Podés asignar una
                    ahora: se cancela el presupuesto actual y se coordina una visita con ese
                    contratista.
                  </Text>
                  <Radio.Group value={ofertaElegida} onChange={setOfertaElegida}>
                    <Stack gap="xs">
                      {ofertasReutilizables.map((oferta) => (
                        <Radio
                          key={oferta.presupuesto_id}
                          value={String(oferta.presupuesto_id)}
                          label={`${oferta.nombre_empresa} — ${formatoMoneda.format(oferta.monto)}`}
                        />
                      ))}
                    </Stack>
                  </Radio.Group>
                  <Button
                    color="teal"
                    loading={asignandoOferta}
                    disabled={!ofertaElegida}
                    onClick={elegirOfertaExistente}
                  >
                    Asignar esta oferta
                  </Button>
                </>
              )}
              <Text size="sm" c={ofertasReutilizables.length > 0 ? 'dimmed' : undefined}>
                {ofertasReutilizables.length > 0
                  ? 'O cancelá el presupuesto aprobado y volvé a convocar a otros contratistas.'
                  : 'Se rechaza el presupuesto aprobado, se cancela la visita y el reclamo vuelve a pendiente de presupuesto. Se avisa por WhatsApp a la escuela y al contratista.'}
              </Text>
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setConfirmarReabrir(false)}>
                  Volver
                </Button>
                <Button
                  color="orange"
                  variant={ofertasReutilizables.length > 0 ? 'light' : 'filled'}
                  loading={reabriendo}
                  onClick={cancelarPresupuestoYConvocar}
                >
                  Convocar a otros
                </Button>
              </Group>
            </Stack>
          </Modal>

          <ChangeStatusModal
            reclamo={cambiarEstadoAbierto ? reclamo : null}
            onClose={() => setCambiarEstadoAbierto(false)}
            onEstadoCambiado={() => {
              setCambiarEstadoAbierto(false);
              setRecarga((n) => n + 1);
              onReclamoActualizado?.();
            }}
          />
        </>
      )}
    </Drawer>
  );
}
