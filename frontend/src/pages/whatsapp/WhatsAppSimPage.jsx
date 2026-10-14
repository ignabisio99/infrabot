import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import {
  IconCalendarTime,
  IconClock,
  IconClockPlay,
  IconInbox,
  IconMicrophone,
  IconPaperclip,
  IconRefresh,
  IconRotateClockwise2,
  IconSend,
  IconSettings,
} from '@tabler/icons-react';

import {
  reiniciarSimuladorWhatsApp,
  simularWhatsAppMedia,
  simularWhatsAppTexto,
} from '../../api/whatsappSim';
import {
  avanzarTiempo,
  obtenerEstadoSimulador,
  obtenerMensajesSalientes,
  resetearTiempo,
} from '../../api/simuladorTiempo';
import { esAdministrador } from '../../utils/auth';
import { SimuladorTiempoModal } from '../../components/SimuladorTiempoModal';
import { useGrabarAudio } from '../../hooks/useGrabarAudio';
import { notifyError, notifySuccess } from '../../utils/notifications';

const ORIGEN_DEFAULT = 'sim5491100000000';
const ORIGEN_KEY = 'infrabot_whatsapp_sim_origen';

function etiquetaStt(proveedor) {
  if (proveedor === 'local') return 'Whisper small';
  return proveedor || '';
}

function claveMensajes(origen) {
  return `infrabot_whatsapp_sim_msgs:${(origen || '').trim() || ORIGEN_DEFAULT}`;
}

function leerOrigenGuardado() {
  try {
    return localStorage.getItem(ORIGEN_KEY) || ORIGEN_DEFAULT;
  } catch {
    return ORIGEN_DEFAULT;
  }
}

function leerMensajes(origen) {
  try {
    const parsed = JSON.parse(localStorage.getItem(claveMensajes(origen)) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function burbuja(de, contenido) {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    de,
    ...contenido,
  };
}

export function WhatsAppSimPage() {
  const esAdmin = esAdministrador();
  const [origen, setOrigen] = useState(leerOrigenGuardado);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [mensajes, setMensajes] = useState(() => leerMensajes(leerOrigenGuardado()));
  const [modalSimuladorAbierto, setModalSimuladorAbierto] = useState(false);
  const [estadoReloj, setEstadoReloj] = useState(null);
  const [avanzandoReloj, setAvanzandoReloj] = useState(false);
  const abajo = useRef(null);
  const adjuntoRef = useRef(null);
  const origenRef = useRef(origen);
  const { grabando, empezar, detener } = useGrabarAudio();

  const sincronizarMensajesBot = async (numeroAUsar = origen) => {
    if (!numeroAUsar) return;
    try {
      const salientes = await obtenerMensajesSalientes(numeroAUsar, 15);
      if (salientes && salientes.length > 0) {
        setMensajes((actuales) => {
          const idsExistentes = new Set(actuales.map((m) => m.id));
          const textosExistentes = new Set(actuales.filter((m) => m.de === 'bot').map((m) => m.texto));
          const nuevos = [];

          for (const s of salientes) {
            if (!idsExistentes.has(s.id) && !textosExistentes.has(s.body)) {
              nuevos.push({
                id: s.id,
                de: 'bot',
                texto: s.body,
                botones: s.botones || [],
                secciones: s.secciones || [],
                tipo: s.tipo,
              });
              idsExistentes.add(s.id);
              textosExistentes.add(s.body);
            }
          }

          if (nuevos.length === 0) return actuales;
          return [...actuales, ...nuevos];
        });
      }
    } catch {
      // Ignorar si falla
    }
  };

  const handleAvanzarTiempo = async (params) => {
    try {
      setAvanzandoReloj(true);
      const res = await avanzarTiempo(params);
      setEstadoReloj(res);
      notifySuccess(`Reloj avanzado: ${res.ahora_art}`);
      await sincronizarMensajesBot(origen);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setAvanzandoReloj(false);
    }
  };

  const handleResetTiempo = async () => {
    try {
      setAvanzandoReloj(true);
      const res = await resetearTiempo();
      setEstadoReloj(res);
      notifySuccess('Reloj restablecido a tiempo real.');
    } catch (err) {
      notifyError(err.message);
    } finally {
      setAvanzandoReloj(false);
    }
  };

  useEffect(() => {
    if (esAdmin) {
      obtenerEstadoSimulador().then(setEstadoReloj).catch(() => {});
    }
    sincronizarMensajesBot(origen);
  }, [origen, esAdmin]);

  useEffect(() => {
    abajo.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensajes]);

  useEffect(() => {
    if (origenRef.current !== origen) {
      origenRef.current = origen;
      setMensajes(leerMensajes(origen));
      return;
    }
    try {
      localStorage.setItem(ORIGEN_KEY, origen);
      localStorage.setItem(claveMensajes(origen), JSON.stringify(mensajes));
    } catch {
      // Quota o modo privado: la charla sigue en pantalla.
    }
  }, [origen, mensajes]);

  const agregarRespuesta = (respuesta) => {
    setMensajes((actuales) => [
      ...actuales,
      burbuja('bot', {
        texto: respuesta.body,
        botones: respuesta.botones || [],
        secciones: respuesta.secciones || [],
        botonTexto: respuesta.boton_texto,
        tipo: respuesta.tipo,
      }),
    ]);
  };

  const enviar = async (valor, etiqueta) => {
    const contenido = (valor || '').trim();
    if (!contenido || enviando) return;
    setEnviando(true);
    setMensajes((actuales) => [
      ...actuales,
      burbuja('yo', { texto: etiqueta || contenido, botones: [], secciones: [] }),
    ]);
    setTexto('');
    try {
      const respuesta = await simularWhatsAppTexto(origen, contenido);
      agregarRespuesta(respuesta);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const adjuntar = async (archivo) => {
    if (!archivo || enviando) return;
    const esAudio = archivo.type.startsWith('audio/');
    setEnviando(true);
    const idNota = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setMensajes((actuales) => [
      ...actuales,
      {
        id: idNota,
        de: 'yo',
        texto: esAudio ? '🎤 Nota de voz' : `📎 ${archivo.name}`,
        transcripcion: esAudio ? 'Transcribiendo…' : null,
        proveedorStt: esAudio ? 'local' : null,
        botones: [],
        secciones: [],
      },
    ]);
    try {
      const respuesta = await simularWhatsAppMedia(origen, archivo);
      if (esAudio) {
        setMensajes((actuales) =>
          actuales.map((msg) =>
            msg.id === idNota
              ? {
                  ...msg,
                  transcripcion: respuesta.transcripcion || 'No se pudo transcribir.',
                  proveedorStt: respuesta.proveedor_stt || 'local',
                }
              : msg,
          ),
        );
      }
      agregarRespuesta(respuesta);
    } catch (err) {
      if (esAudio) {
        setMensajes((actuales) =>
          actuales.map((msg) =>
            msg.id === idNota
              ? { ...msg, transcripcion: err.message || 'No se pudo transcribir.' }
              : msg,
          ),
        );
      }
      notifyError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const nuevaCharla = async () => {
    if (enviando || grabando) return;
    try {
      await reiniciarSimuladorWhatsApp(origen);
      setMensajes([]);
      localStorage.removeItem(claveMensajes(origen));
    } catch (err) {
      notifyError(err.message || 'No se pudo empezar una charla nueva.');
    }
  };

  const grabarNota = async () => {
    if (enviando) return;
    try {
      if (!grabando) {
        await empezar();
        return;
      }
      const archivo = await detener();
      if (archivo) await adjuntar(archivo);
    } catch (err) {
      notifyError(err.message || 'No se pudo grabar el audio.');
    }
  };

  const telefonosActivos = [];
  if (estadoReloj?.proximas_visitas) {
    for (const v of estadoReloj.proximas_visitas) {
      if (v.contratista_telefono && !telefonosActivos.some((x) => x.telefono === v.contratista_telefono)) {
        telefonosActivos.push({
          telefono: v.contratista_telefono,
          etiqueta: `Contratista (${v.contratista || `#${v.reclamo_id}`})`,
          color: 'teal',
        });
      }
      if (v.creador_telefono && !telefonosActivos.some((x) => x.telefono === v.creador_telefono)) {
        telefonosActivos.push({
          telefono: v.creador_telefono,
          etiqueta: `Escuela (${v.escuela || `#${v.reclamo_id}`})`,
          color: 'blue',
        });
      }
    }
  }
  if (estadoReloj?.reclamos_en_ejecucion) {
    for (const r of estadoReloj.reclamos_en_ejecucion) {
      if (r.contratista_telefono && !telefonosActivos.some((x) => x.telefono === r.contratista_telefono)) {
        telefonosActivos.push({
          telefono: r.contratista_telefono,
          etiqueta: `Contratista (#${r.id})`,
          color: 'teal',
        });
      }
      if (r.creador_telefono && !telefonosActivos.some((x) => x.telefono === r.creador_telefono)) {
        telefonosActivos.push({
          telefono: r.creador_telefono,
          etiqueta: `Escuela (#${r.id})`,
          color: 'blue',
        });
      }
    }
  }

  return (
    <Container size={560} px="xs">
      <Stack gap="md">
      <div>
        <Title order={2} ta="center">
          Simulador de WhatsApp
        </Title>
        <Text size="sm" c="dimmed" ta="center">
          Habla con el mismo bot que Meta, en tu máquina. No usa ngrok ni Redis.
          Los botones envían el id, igual que en WhatsApp.
        </Text>
      </div>

      {/* Barra de simulación de tiempo exclusiva para administradores */}
      {esAdmin && (
        <Paper
          withBorder
          p="xs"
          radius="md"
          style={{
            background: estadoReloj?.es_simulado
              ? 'linear-gradient(135deg, rgba(255, 146, 43, 0.08) 0%, rgba(255, 107, 107, 0.08) 100%)'
              : '#f8fafc',
            borderColor: estadoReloj?.es_simulado ? '#ffa94d' : undefined,
          }}
        >
          <Group justify="space-between" align="center" mb={6}>
            <Group gap="xs">
              <Badge color={estadoReloj?.es_simulado ? 'orange' : 'teal'} variant="filled" size="sm">
                🕒 {estadoReloj?.es_simulado ? `Simulado (${estadoReloj.offset_descripcion})` : 'Tiempo real'}
              </Badge>
              <Text size="xs" fw={600}>
                {estadoReloj?.ahora_art || ''}
              </Text>
            </Group>
            <Group gap={6}>
              <Button
                size="compact-xs"
                variant="subtle"
                color="teal"
                leftSection={<IconInbox size={12} />}
                onClick={() => sincronizarMensajesBot(origen)}
              >
                Chequear mensajes
              </Button>
              <Button
                size="compact-xs"
                variant="light"
                color="blue"
                leftSection={<IconSettings size={12} />}
                onClick={() => setModalSimuladorAbierto(true)}
              >
                Panel completo
              </Button>
            </Group>
          </Group>

          <Group gap={6} wrap="wrap">
            <Text size="xs" c="dimmed" fw={600}>
              Avanzar:
            </Text>
            <Button
              size="compact-xs"
              variant="light"
              color="teal"
              onClick={() => handleAvanzarTiempo({ horas: 6 })}
              loading={avanzandoReloj}
            >
              +6 h
            </Button>
            <Button
              size="compact-xs"
              variant="light"
              color="teal"
              onClick={() => handleAvanzarTiempo({ horas: 12 })}
              loading={avanzandoReloj}
            >
              +12 h
            </Button>
            <Button
              size="compact-xs"
              variant="filled"
              color="teal"
              onClick={() => handleAvanzarTiempo({ dias: 1 })}
              loading={avanzandoReloj}
            >
              +1 día
            </Button>
            <Button
              size="compact-xs"
              variant="filled"
              color="teal"
              onClick={() => handleAvanzarTiempo({ dias: 2 })}
              loading={avanzandoReloj}
            >
              +2 días
            </Button>
            <Button
              size="compact-xs"
              variant="gradient"
              gradient={{ from: 'teal', to: 'cyan' }}
              onClick={() => handleAvanzarTiempo({ hasta_proxima_visita: true })}
              loading={avanzandoReloj}
            >
              A hora de visita
            </Button>
            {estadoReloj?.es_simulado && (
              <Button
                size="compact-xs"
                variant="subtle"
                color="red"
                leftSection={<IconRotateClockwise2 size={12} />}
                onClick={handleResetTiempo}
                loading={avanzandoReloj}
              >
                Reset
              </Button>
            )}
          </Group>
        </Paper>
      )}

      <TextInput
        label="Número simulado"
        description="Identifica esta charla. No es un WhatsApp real."
        value={origen}
        onChange={(e) => setOrigen(e.currentTarget.value)}
      />

      {/* Selector rápido de números activos */}
      {telefonosActivos.length > 0 && (
        <Group gap={6} wrap="wrap">
          <Text size="xs" c="dimmed">
            Accesos directos:
          </Text>
          {telefonosActivos.map((t) => (
            <Button
              key={t.telefono}
              size="compact-xs"
              variant={origen === t.telefono ? 'filled' : 'light'}
              color={t.color}
              onClick={() => setOrigen(t.telefono)}
            >
              {t.etiqueta}: {t.telefono}
            </Button>
          ))}
        </Group>
      )}

      <Paper
        withBorder
        radius="md"
        p="sm"
        style={{ background: '#0b141a' }}
      >
        <Group justify="space-between" mb="xs" wrap="nowrap">
          <Text size="sm" c="gray.4" fw={600}>
            InfraBot
          </Text>
          <Group gap={6} wrap="nowrap">
            <Button
              type="button"
              size="xs"
              variant="subtle"
              color="gray"
              leftSection={<IconRefresh size={14} />}
              onClick={nuevaCharla}
              disabled={enviando || grabando}
            >
              Empezar nueva charla
            </Button>
            <Badge size="xs" variant="light" color="green">
              local
            </Badge>
          </Group>
        </Group>
        <ScrollArea h={420} offsetScrollbars>
          <Stack gap="xs" p={4}>
            {mensajes.length === 0 && (
              <Text size="sm" c="dimmed" ta="center" py="xl">
                Escribí hola o ayuda para ver el menú.
              </Text>
            )}
            {mensajes.map((msg) => (
              <Paper
                key={msg.id}
                p="xs"
                radius="md"
                maw="85%"
                style={{
                  alignSelf: msg.de === 'yo' ? 'flex-end' : 'flex-start',
                  background: msg.de === 'yo' ? '#005c4b' : '#202c33',
                }}
              >
                <Text size="sm" c="gray.1" style={{ whiteSpace: 'pre-wrap' }}>
                  {msg.texto}
                </Text>
                {msg.transcripcion && (
                  <Text size="xs" c="gray.4" mt={4} style={{ whiteSpace: 'pre-wrap' }}>
                    {msg.transcripcion}
                    {msg.proveedorStt ? ` (${etiquetaStt(msg.proveedorStt)})` : ''}
                  </Text>
                )}
                {msg.botones?.length > 0 && (
                  <Stack gap={6} mt="xs">
                    {msg.botones.map((boton) => (
                      <Button
                        key={boton.id}
                        size="xs"
                        variant="light"
                        color="teal"
                        onClick={() => enviar(boton.id, boton.title)}
                        disabled={enviando}
                      >
                        {boton.title}
                      </Button>
                    ))}
                  </Stack>
                )}
                {msg.secciones?.length > 0 && (
                  <Stack gap={6} mt="xs">
                    {msg.secciones.flatMap((seccion) =>
                      (seccion.rows || []).map((fila) => (
                        <Button
                          key={fila.id}
                          size="xs"
                          variant="light"
                          color="teal"
                          onClick={() => enviar(fila.id, fila.title)}
                          disabled={enviando}
                        >
                          {fila.title}
                        </Button>
                      )),
                    )}
                  </Stack>
                )}
              </Paper>
            ))}
            <div ref={abajo} />
          </Stack>
        </ScrollArea>
      </Paper>

      <input
        ref={adjuntoRef}
        type="file"
        accept="image/*,video/*"
        hidden
        onChange={(e) => {
          const archivo = e.currentTarget.files?.[0];
          e.currentTarget.value = '';
          if (archivo) adjuntar(archivo);
        }}
      />
      <Group align="flex-end" wrap="nowrap">
        <Button
          type="button"
          variant="default"
          px="sm"
          disabled={enviando || grabando}
          title="Adjuntar foto o video"
          onClick={() => adjuntoRef.current?.click()}
        >
          <IconPaperclip size={18} />
        </Button>
        <Button
          type="button"
          variant={grabando ? 'filled' : 'light'}
          color={grabando ? 'red' : 'teal'}
          disabled={enviando}
          onClick={grabarNota}
          leftSection={<IconMicrophone size={18} />}
        >
          {grabando ? 'Enviar nota' : 'Grabar nota'}
        </Button>
        <TextInput
          style={{ flex: 1 }}
          placeholder="Escribí un mensaje…"
          value={texto}
          onChange={(e) => setTexto(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') enviar(texto);
          }}
          disabled={enviando}
        />
        <Button
          onClick={() => enviar(texto)}
          loading={enviando}
          leftSection={<IconSend size={16} />}
        >
          Enviar
        </Button>
      </Group>
      </Stack>

      <SimuladorTiempoModal
        opened={modalSimuladorAbierto}
        onClose={() => setModalSimuladorAbierto(false)}
        onTiempoActualizado={(n) => {
          setEstadoReloj(n);
          sincronizarMensajesBot(origen);
        }}
      />
    </Container>
  );
}
