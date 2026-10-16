import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Paper,
  ScrollArea,
  Select,
  Stack,
  Tabs,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { IconSend } from '@tabler/icons-react';

import {
  cerrarConversacion,
  enviarMensajeOperador,
  liberarConversacion,
  listarHistorial,
  listarMensajes,
  listarOperadores,
  reabrirConversacion,
  tomarConversacion,
  transferirConversacion,
} from '../../api/conversaciones';
import { getUsuarioActual } from '../../utils/auth';
import { formatoHoraMensaje } from '../../utils/formatters';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { useConversaciones } from './ConversacionesContext';
import { HiloChat } from './HiloChat';

function fusionarMensajes(actuales, incoming) {
  const map = new Map();
  [...(actuales || []), ...(incoming || [])].forEach((m) => {
    if (m?.id != null) map.set(m.id, m);
  });
  const fusion = [...map.values()].sort((a, b) => a.id - b.id);
  if (
    actuales?.length === fusion.length &&
    actuales.every((m, i) => m.id === fusion[i].id && m.texto === fusion[i].texto)
  ) {
    return actuales;
  }
  return fusion;
}

function etiquetaEstado(conv) {
  if (conv.estado === 'ESPERANDO_OPERADOR') return 'En espera';
  if (conv.estado === 'CERRADA') return 'Cerrada';
  return 'Asignada';
}

function ItemBandeja({ conv, activo, tieneNuevos, onClick }) {
  return (
    <Paper
      withBorder
      p="sm"
      radius="md"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderColor: activo ? '#1fa7b3' : undefined,
        background: activo ? 'rgba(31, 167, 179, 0.08)' : undefined,
      }}
    >
      <Group justify="space-between" wrap="nowrap" gap={8}>
        <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
          {tieneNuevos && (
            <Box
              w={8}
              h={8}
              style={{ borderRadius: '50%', background: 'var(--mantine-color-red-6)', flexShrink: 0 }}
            />
          )}
          <Text fw={tieneNuevos ? 700 : 600} size="sm" truncate>
            {conv.telefono}
          </Text>
        </Group>
        <Group gap={6} wrap="nowrap" style={{ flexShrink: 0 }}>
          {formatoHoraMensaje(conv.ultimo_fecha) ? (
            <Text size="xs" c="dimmed">
              {formatoHoraMensaje(conv.ultimo_fecha)}
            </Text>
          ) : null}
          <Badge
            size="xs"
            variant="light"
            color={
              conv.estado === 'ESPERANDO_OPERADOR'
                ? 'orange'
                : conv.estado === 'CERRADA'
                  ? 'gray'
                  : 'teal'
            }
          >
            {etiquetaEstado(conv)}
          </Badge>
        </Group>
      </Group>
      <Text size="xs" c="dimmed" lineClamp={2} mt={4}>
        {conv.ultimo_texto || 'Sin mensajes'}
      </Text>
    </Paper>
  );
}

export function ConversacionesPage() {
  const { enEspera, mias, conNuevos, miasNuevosCount, setChatAbierto, recargar } =
    useConversaciones();
  const yo = getUsuarioActual()?.id;
  const [tab, setTab] = useState('espera');
  const [seleccion, setSeleccion] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [transferirAbierto, setTransferirAbierto] = useState(false);
  const [operadores, setOperadores] = useState([]);
  const [destino, setDestino] = useState(null);
  const [historial, setHistorial] = useState([]);
  const abajo = useRef(null);

  const lista = tab === 'espera' ? enEspera : tab === 'mias' ? mias : historial;
  const esHistorial = tab === 'historial';

  const esMia = seleccion && seleccion.estado === 'CON_OPERADOR' && seleccion.operador_id === yo;
  const enEsperaSel = seleccion && seleccion.estado === 'ESPERANDO_OPERADOR';
  const avisoAjena =
    seleccion &&
    seleccion.estado === 'CON_OPERADOR' &&
    seleccion.operador_id != null &&
    seleccion.operador_id !== yo
      ? `${seleccion.operador_nombre || 'Otro operador'} tomó esta conversación.`
      : '';
  const puedeEscribir = Boolean(esMia && seleccion?.ventana_abierta && !avisoAjena);

  useEffect(() => {
    abajo.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensajes]);

  useEffect(() => {
    return () => setChatAbierto(null);
  }, []);

  useEffect(() => {
    if (tab !== 'historial') return undefined;
    let cancelado = false;
    listarHistorial()
      .then((data) => {
        if (!cancelado) setHistorial(data);
      })
      .catch((err) => notifyError(err.message));
    return () => {
      cancelado = true;
    };
  }, [tab]);

  useEffect(() => {
    if (!seleccion) return undefined;
    const chatId = seleccion.id;
    let cancelado = false;
    const cargar = () =>
      listarMensajes(chatId)
        .then((data) => {
          if (!cancelado) {
            setMensajes((actuales) => fusionarMensajes(actuales, data));
          }
        })
        .catch((err) => notifyError(err.message));
    cargar();
    const id = setInterval(cargar, 4000);
    return () => {
      cancelado = true;
      clearInterval(id);
    };
  }, [seleccion?.id]);

  const abrir = (conv) => {
    setSeleccion(conv);
    setMensajes([]);
    setTexto('');
    if (tab === 'historial') {
      setChatAbierto(null);
      return;
    }
    setTab('mias');
    setChatAbierto(conv.id, conv.ultimo_id);
  };

  const cambiarTab = (value) => {
    if (!value || value === tab) return;
    setTab(value);
    if (value !== 'mias') {
      setChatAbierto(null);
      return;
    }
    if (seleccion?.estado === 'CON_OPERADOR') {
      setChatAbierto(seleccion.id, seleccion.ultimo_id);
    }
  };

  const actuar = async (fn, ok, { cerrarVista } = {}) => {
    if (!seleccion) return false;
    try {
      const actualizada = await fn(seleccion.id);
      recargar();
      if (cerrarVista) {
        setChatAbierto(null);
        setSeleccion(null);
      } else {
        setSeleccion(actualizada);
        if (actualizada?.id) setChatAbierto(actualizada.id, actualizada.ultimo_id);
      }
      if (ok) notifySuccess(ok);
      return true;
    } catch (err) {
      notifyError(err.message);
      recargar();
      return false;
    }
  };

  const enviar = async () => {
    const valor = texto.trim();
    if (!valor || !seleccion || !puedeEscribir || enviando) return;
    setEnviando(true);
    try {
      const creado = await enviarMensajeOperador(seleccion.id, valor);
      setMensajes((actuales) => fusionarMensajes(actuales, [creado]));
      setTexto('');
    } catch (err) {
      notifyError(err.message);
    } finally {
      try {
        const lista = await listarMensajes(seleccion.id);
        setMensajes((actuales) => fusionarMensajes(actuales, lista));
      } catch {
        // El poll del chat reintenta.
      }
      setEnviando(false);
    }
  };

  const abrirTransferir = async () => {
    try {
      const listaOps = await listarOperadores();
      setOperadores(listaOps);
      setDestino(null);
      setTransferirAbierto(true);
    } catch (err) {
      notifyError(err.message);
    }
  };

  const confirmarTransferir = async () => {
    if (!destino || !seleccion) return;
    try {
      const actualizada = await transferirConversacion(seleccion.id, Number(destino));
      setSeleccion(actualizada);
      setTransferirAbierto(false);
      recargar();
      notifySuccess('Conversación transferida.');
    } catch (err) {
      notifyError(err.message);
    }
  };

  const opcionesOps = useMemo(
    () => operadores.map((o) => ({ value: String(o.id), label: o.nombre })),
    [operadores],
  );

  return (
    <Box h="calc(100vh - 120px)" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <Title order={2} mb="sm">
        Conversaciones
      </Title>
      <Group align="stretch" wrap="nowrap" gap="md" style={{ flex: 1, minHeight: 0 }}>
        <Paper withBorder p="sm" w={360} style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Tabs value={tab} onChange={cambiarTab}>
            <Tabs.List grow>
              <Tabs.Tab
                value="espera"
                px="md"
                rightSection={
                  enEspera.length > 0 ? (
                    <Badge size="sm" circle color="red">
                      {enEspera.length}
                    </Badge>
                  ) : undefined
                }
              >
                En espera
              </Tabs.Tab>
              <Tabs.Tab
                value="mias"
                px="md"
                rightSection={
                  miasNuevosCount > 0 ? (
                    <Badge size="sm" circle color="red">
                      {miasNuevosCount}
                    </Badge>
                  ) : undefined
                }
              >
                Mías
              </Tabs.Tab>
              <Tabs.Tab value="historial" px="md">
                Historial
              </Tabs.Tab>
            </Tabs.List>
          </Tabs>
          <ScrollArea style={{ flex: 1 }} mt="sm" offsetScrollbars>
            <Stack gap="xs">
              {lista.length === 0 && (
                <Text size="sm" c="dimmed" ta="center" py="xl">
                  No hay chats acá.
                </Text>
              )}
              {lista.map((conv) => (
                <ItemBandeja
                  key={conv.id}
                  conv={conv}
                  activo={seleccion?.id === conv.id}
                  tieneNuevos={[...conNuevos].some((id) => Number(id) === Number(conv.id))}
                  onClick={() => abrir(conv)}
                />
              ))}
            </Stack>
          </ScrollArea>
        </Paper>

        <Paper
          withBorder
          p="md"
          style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
          {!seleccion ? (
            <Text c="dimmed" ta="center" py="xl">
              Elegí un chat de la bandeja.
            </Text>
          ) : (
            <Stack gap="sm" style={{ flex: 1, minHeight: 0 }}>
              <Group justify="space-between">
                <div>
                  <Text fw={600}>{seleccion.telefono}</Text>
                  <Text size="xs" c="dimmed">
                    {seleccion.operador_nombre
                      ? `Operador: ${seleccion.operador_nombre}`
                      : 'Sin asignar'}
                    {seleccion.ventana_abierta ? '' : ' · Ventana de 24 h vencida'}
                  </Text>
                </div>
                <Group gap={6}>
                  {enEsperaSel && (
                    <Button
                      size="xs"
                      onClick={async () => {
                        if (await actuar(tomarConversacion, 'Tomaste el chat.')) setTab('mias');
                      }}
                    >
                      Tomar
                    </Button>
                  )}
                  {esHistorial &&
                    seleccion.estado === 'CERRADA' &&
                    seleccion.ventana_abierta && (
                      <Button
                        size="xs"
                        onClick={async () => {
                          if (await actuar(reabrirConversacion, 'Reabriste el chat.')) {
                            setTab('mias');
                          }
                        }}
                      >
                        Reabrir
                      </Button>
                    )}
                  {esMia && (
                    <>
                      <Button size="xs" variant="light" onClick={abrirTransferir}>
                        Transferir
                      </Button>
                      <Button
                        size="xs"
                        variant="light"
                        color="orange"
                        onClick={() =>
                          actuar(liberarConversacion, 'Liberaste el chat. El bot vuelve a atender.', {
                            cerrarVista: true,
                          })
                        }
                      >
                        Liberar
                      </Button>
                      <Button
                        size="xs"
                        color="gray"
                        variant="light"
                        onClick={() =>
                          actuar(cerrarConversacion, 'Chat cerrado. El bot vuelve a atender.', {
                            cerrarVista: true,
                          })
                        }
                      >
                        Cerrar
                      </Button>
                    </>
                  )}
                </Group>
              </Group>

              {avisoAjena && <Alert color="yellow">{avisoAjena}</Alert>}
              {esMia && !seleccion.ventana_abierta && (
                <Alert color="orange">
                  Pasaron más de 24 horas desde el último mensaje del usuario. WhatsApp no permite
                  responder hasta que escriba de nuevo.
                </Alert>
              )}

              <ScrollArea style={{ flex: 1 }} offsetScrollbars>
                <HiloChat mensajes={mensajes} pie={<div ref={abajo} />} />
              </ScrollArea>

              {!esHistorial && (
                <Group align="flex-end" wrap="nowrap">
                  <Textarea
                    style={{ flex: 1 }}
                    minRows={3}
                    maxRows={8}
                    autosize
                    maxLength={4096}
                    placeholder={puedeEscribir ? 'Escribí un mensaje…' : 'No podés responder este chat'}
                    value={texto}
                    onChange={(e) => setTexto(e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        enviar();
                      }
                    }}
                    disabled={!puedeEscribir || enviando}
                  />
                  <Button
                    onClick={enviar}
                    loading={enviando}
                    disabled={!puedeEscribir}
                    leftSection={<IconSend size={16} />}
                  >
                    Enviar
                  </Button>
                </Group>
              )}
            </Stack>
          )}
        </Paper>
      </Group>

      <Modal
        opened={transferirAbierto}
        onClose={() => setTransferirAbierto(false)}
        title="Transferir conversación"
      >
        <Stack>
          <Select
            label="Operador"
            placeholder="Elegí un administrador"
            data={opcionesOps}
            value={destino}
            onChange={setDestino}
          />
          <Button type="button" onClick={confirmarTransferir} disabled={!destino}>
            Transferir
          </Button>
        </Stack>
      </Modal>
    </Box>
  );
}
