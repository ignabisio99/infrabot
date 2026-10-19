import { useEffect, useRef, useState } from 'react';
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
  IconArrowsMaximize,
  IconArrowsMinimize,
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
import { historialPorTelefono } from '../../api/conversaciones';
import { formatoMoneda } from '../../utils/formatters';
import { avisarNotificacionesCambiaron } from '../../layout/NotificationBell';
import { formatearIdReclamo } from '../../utils/ids';
import { esAdministrador, esInspector, getUsuarioActual } from '../../utils/auth';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { HiloChat } from '../conversaciones/HiloChat';
import { BudgetRequestsList } from './BudgetRequestsList';
import { ChangeStatusModal } from './ChangeStatusModal';
import { ClaimCommentsThread } from './ClaimComments';
import { esComentarioContratista, partesComentarioContratista } from './comentariosContratista';
import { ClaimIAPanel } from './ClaimIAPanel';
import { ClaimPhotosManager } from './ClaimPhotosManager';
import { NotifyContractorsModal } from './NotifyContractorsModal';
import { PriorityBadge } from './PriorityBadge';
import { StatusBadge } from './StatusBadge';
import tabsClasses from './ClaimDetailTabs.module.css';
import { colorPorEstado, estadosFinales, etiquetaPorEstado, proximoPasoPorEstado } from './estados';

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
const AYUDA_INSPECTOR_FOTOS =
  ' En la pestaña Fotos podés agregar fotos y quitar las que subiste; si quitás una, queda registrado acá.';
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

const PAGINA_CHAT_RECLAMO = 30;

function ChatDelReclamo({ telefono }) {
  const [abierto, setAbierto] = useState(false);
  const [ampliado, setAmpliado] = useState(false);
  const [mensajes, setMensajes] = useState([]);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [cargandoMas, setCargandoMas] = useState(false);
  const [error, setError] = useState(null);
  const viewport = useRef(null);

  const irAlFinal = () => {
    const el = viewport.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => {
    if (!abierto) return undefined;
    let vigente = true;
    setCargando(true);
    historialPorTelefono(telefono, { limit: PAGINA_CHAT_RECLAMO })
      .then((data) => {
        if (!vigente) return;
        setMensajes(data.mensajes);
        setHayMas(data.hay_mas);
        setError(null);
        window.setTimeout(irAlFinal, 80);
      })
      .catch((err) => {
        if (vigente) setError(err.message);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [telefono, abierto]);

  useEffect(() => {
    if (!abierto || cargando || mensajes.length === 0) return undefined;
    const t1 = window.setTimeout(irAlFinal, 50);
    const t2 = window.setTimeout(irAlFinal, 280);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [abierto, ampliado, cargando, mensajes.length]);

  const cargarMas = () => {
    if (!mensajes.length || cargandoMas) return;
    const el = viewport.current;
    const previa = el?.scrollHeight ?? 0;
    const top = el?.scrollTop ?? 0;
    setCargandoMas(true);
    historialPorTelefono(telefono, { limit: PAGINA_CHAT_RECLAMO, antesDe: mensajes[0].id })
      .then((data) => {
        setMensajes((prev) => [...data.mensajes, ...prev]);
        setHayMas(data.hay_mas);
        requestAnimationFrame(() => {
          if (el) el.scrollTop = top + (el.scrollHeight - previa);
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargandoMas(false));
  };

  const hilo = (
    <Stack gap={6} mt={ampliado ? 0 : 'xs'}>
      {hayMas && (
        <Button variant="subtle" size="compact-xs" loading={cargandoMas} onClick={cargarMas}>
          Cargar mensajes anteriores
        </Button>
      )}
      <div
        ref={viewport}
        style={{
          height: ampliado ? '70vh' : 360,
          overflow: 'auto',
        }}
      >
        <HiloChat mensajes={mensajes} />
      </div>
    </Stack>
  );

  return (
    <Paper withBorder p="xs" radius="md">
      <Group justify="space-between" gap="xs">
        <Text size="sm" fw={600}>
          Chat de WhatsApp
        </Text>
        <Group gap={4}>
          {abierto && !cargando && mensajes.length > 0 && (
            <Button
              variant="subtle"
              size="compact-xs"
              leftSection={
                ampliado ? <IconArrowsMinimize size={14} /> : <IconArrowsMaximize size={14} />
              }
              onClick={() => setAmpliado((v) => !v)}
            >
              {ampliado ? 'Reducir' : 'Expandir'}
            </Button>
          )}
          <Button
            variant="subtle"
            size="compact-xs"
            onClick={() => {
              setAbierto((v) => !v);
              setAmpliado(false);
            }}
          >
            {abierto ? 'Cerrar' : 'Ver chat'}
          </Button>
        </Group>
      </Group>
      {abierto && cargando && <Loader size="sm" mt="xs" />}
      {abierto && !cargando && error && (
        <Text size="sm" c="dimmed" mt="xs">
          No se pudo cargar el chat.
        </Text>
      )}
      {abierto && !cargando && !error && mensajes.length === 0 && (
        <Text size="sm" c="dimmed" mt="xs">
          No hay mensajes de WhatsApp para este número.
        </Text>
      )}
      {abierto && !cargando && !error && mensajes.length > 0 && !ampliado && hilo}
      <Modal
        opened={ampliado}
        onClose={() => setAmpliado(false)}
        title="Chat de WhatsApp"
        size="lg"
        centered
        transitionProps={{ onEntered: irAlFinal }}
      >
        {hilo}
      </Modal>
    </Paper>
  );
}

/**
 * Cuelga cada comentario del contratista del último cambio de estado anterior a su fecha
 * (en obra, "Pasó a En ejecución"). Devuelve un array paralelo a `historial`.
 */
function comentariosPorEvento(historial, comentariosContratista) {
  const porEvento = historial.map(() => []);
  if (historial.length === 0) return porEvento;
  for (const comentario of comentariosContratista) {
    const fecha = new Date(comentario.fecha);
    let indice = 0;
    historial.forEach((evento, i) => {
      if (new Date(evento.fecha) <= fecha) indice = i;
    });
    porEvento[indice].push(comentario);
  }
  return porEvento;
}

function ComentarioContratista({ comentario }) {
  const { empresa, texto } = partesComentarioContratista(comentario);
  return (
    <Paper withBorder radius="md" p="xs">
      <Group justify="space-between" gap="xs" mb={2} wrap="nowrap">
        <Group gap={4} wrap="nowrap" c="dimmed">
          <IconBrandWhatsapp size={14} />
          <Text size="xs" fw={600}>
            {empresa}
          </Text>
        </Group>
        <Text size="xs" c="dimmed">
          {new Date(comentario.fecha).toLocaleString('es-AR')}
        </Text>
      </Group>
      <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
        {texto}
      </Text>
    </Paper>
  );
}

const SIN_CARGAR = {
  id: null,
  reclamo: null,
  historial: [],
  visita: null,
  comentarios: [],
};

export function ClaimDetailDrawer({ reclamoId, onClose, onAbrirReclamo, onReclamoActualizado }) {
  // Guarda el último fetch resuelto junto con el id al que corresponde: así `cargando`
  // se puede derivar comparando contra `reclamoId` en vez de duplicar estado, y una
  // respuesta vieja que llega tarde (ej. al cambiar rápido de reclamo) no pisa una más nueva.
  const [ultimoCargado, setUltimoCargado] = useState(SIN_CARGAR);
  const [recarga, setRecarga] = useState(0);

  // Cada apertura vuelve a cargar todo: al cerrar o cambiar de reclamo se descarta lo que
  // había, así no se muestra la versión anterior mientras llega la nueva y los hijos que
  // copian props a su estado (ej. las fotos) no se montan con datos viejos.
  const [reclamoIdPrevio, setReclamoIdPrevio] = useState(reclamoId);
  if (reclamoId !== reclamoIdPrevio) {
    setReclamoIdPrevio(reclamoId);
    setUltimoCargado(SIN_CARGAR);
  }

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
  const todosComentarios = cargadoCoincide ? ultimoCargado.comentarios : [];
  const comentarios = todosComentarios.filter((c) => !esComentarioContratista(c));
  const avancesPorEvento = comentariosPorEvento(
    historial,
    todosComentarios.filter(esComentarioContratista),
  );
  const cargando = reclamoId !== null && reclamo === null;

  const proximoPaso = reclamo ? proximoPasoPorEstado[reclamo.estado] : null;
  const esAdmin = esAdministrador();
  const inspector = esInspector();
  const puedeCambiarEstado = esAdmin && (reclamo?.estados_posibles?.length ?? 0) > 0;
  const puedeNotificar = esAdmin && reclamo?.estado === 'PENDIENTE_PRESUPUESTO';
  const pendienteIntervencion = reclamo?.estado === 'PENDIENTE_INTERVENCION';
  const reclamoAbierto = reclamo ? !estadosFinales.includes(reclamo.estado) : false;

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

  const abrirCambioContratista = () => {
    setConfirmarReabrir(true);
    setCargandoOfertas(true);
    setOfertaElegida(null);
    listarOfertasReutilizables(reclamo.id)
      .then(setOfertasReutilizables)
      .catch((err) => {
        notifyError(err.message);
        setOfertasReutilizables([]);
      })
      .finally(() => setCargandoOfertas(false));
  };

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
        header: {
          borderBottom: '1px solid var(--mantine-color-gray-3)',
          paddingBottom: 12,
          alignItems: 'flex-start',
        },
        body: { paddingTop: 16, overflowY: 'auto' },
      }}
    >
      {cargando && <Loader />}

      {!cargando && reclamo && (
        <>
          {reclamo.telefono_creador && (
            <Stack gap="xs" mb="md">
              <Group gap={6} c="dimmed">
                <IconBrandWhatsapp size={15} color="var(--mantine-color-teal-6)" />
                <Text size="sm">
                  Creado desde WhatsApp por{' '}
                  <Text span fw={600} c="dark">
                    {reclamo.telefono_creador}
                  </Text>
                </Text>
              </Group>
              {esAdmin && <ChatDelReclamo telefono={reclamo.telefono_creador} />}
            </Stack>
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
                El contratista no respondió los recordatorios de avance. Si hablaste con él y sigue
                en obra, volvé a ejecución. Si no, podés elegir otra oferta que ya se había enviado
                o convocar a otros contratistas.
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
                  <Button color="orange" onClick={abrirCambioContratista}>
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

          <Tabs defaultValue="avance" classNames={tabsClasses}>
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
                  {historial.map((evento, i) => {
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
                        {avancesPorEvento[i].length > 0 && (
                          <Stack gap="xs" mt="sm">
                            {avancesPorEvento[i].map((comentario) => (
                              <ComentarioContratista key={comentario.id} comentario={comentario} />
                            ))}
                          </Stack>
                        )}
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
                puedeSubir={inspector && reclamoAbierto}
                puedeEliminarFoto={(foto) =>
                  inspector && reclamoAbierto && foto.usuario_id === getUsuarioActual()?.id
                }
                // Al quitar una foto el backend deja un comentario: recargar para verlo.
                onFotoEliminada={() => setRecarga((n) => n + 1)}
              />
            </Tabs.Panel>

            <Tabs.Panel value="comentarios" pt="md">
              <Group gap={6} mb="sm" wrap="nowrap" align="flex-start" c="dimmed">
                <IconInfoCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                <Text size="sm">
                  {inspector
                    ? AYUDA_INSPECTOR + (reclamoAbierto ? AYUDA_INSPECTOR_FOTOS : '')
                    : AYUDA_COMENTARIOS}
                </Text>
              </Group>
              <ClaimCommentsThread
                reclamoId={reclamo.id}
                comentarios={comentarios}
                puedeComentar={inspector && reclamoAbierto}
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
                    Hay ofertas que ya se habían enviado y no se eligieron. Podés asignar una ahora:
                    se cancela el presupuesto actual y se coordina una visita con ese contratista.
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
