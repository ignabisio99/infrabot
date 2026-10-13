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
import { IconMicrophone, IconPaperclip, IconRefresh, IconSend } from '@tabler/icons-react';

import {
  reiniciarSimuladorWhatsApp,
  simularWhatsAppMedia,
  simularWhatsAppTexto,
} from '../../api/whatsappSim';
import { useGrabarAudio } from '../../hooks/useGrabarAudio';
import { notifyError } from '../../utils/notifications';

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
  const [origen, setOrigen] = useState(leerOrigenGuardado);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [mensajes, setMensajes] = useState(() => leerMensajes(leerOrigenGuardado()));
  const abajo = useRef(null);
  const adjuntoRef = useRef(null);
  const origenRef = useRef(origen);
  const { grabando, empezar, detener } = useGrabarAudio();

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

  return (
    <Container size={520} px="xs">
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

      <Alert color="blue">
        Los mensajes se guardan en este navegador. Si reiniciás el backend, el
        bot pierde el paso a paso (el reclamo ya confirmado queda en la base).
        Usá “Empezar nueva charla” para resetear.
      </Alert>

      <TextInput
        label="Número simulado"
        description="Identifica esta charla. No es un WhatsApp real."
        value={origen}
        onChange={(e) => setOrigen(e.currentTarget.value)}
      />

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
    </Container>
  );
}
