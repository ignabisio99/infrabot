import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  FileButton,
  Group,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconPaperclip, IconSend } from '@tabler/icons-react';

import { simularWhatsAppMedia, simularWhatsAppTexto } from '../../api/whatsappSim';
import { notifyError } from '../../utils/notifications';

const ORIGEN_DEFAULT = 'sim5491100000000';

function burbuja(de, contenido) {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    de,
    ...contenido,
  };
}

export function WhatsAppSimPage() {
  const [origen, setOrigen] = useState(ORIGEN_DEFAULT);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [mensajes, setMensajes] = useState([]);
  const abajo = useRef(null);

  useEffect(() => {
    abajo.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensajes]);

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
    setEnviando(true);
    setMensajes((actuales) => [
      ...actuales,
      burbuja('yo', { texto: `📎 ${archivo.name}`, botones: [], secciones: [] }),
    ]);
    try {
      const respuesta = await simularWhatsAppMedia(origen, archivo);
      agregarRespuesta(respuesta);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Stack gap="md" maw={720}>
      <div>
        <Title order={2}>Simulador de WhatsApp</Title>
        <Text size="sm" c="dimmed">
          Habla con el mismo bot que Meta, en tu máquina. No usa ngrok ni Redis.
          Los botones envían el id, igual que en WhatsApp.
        </Text>
      </div>

      <Alert color="blue">
        El estado de la conversación vive en memoria del backend. Si recargás el
        contenedor, se pierde el paso a paso (el reclamo ya confirmado queda en la
        base). Cambiá el “número simulado” si querés otra conversación en paralelo.
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
        <Group justify="space-between" mb="xs">
          <Text size="sm" c="gray.4" fw={600}>
            InfraBot
          </Text>
          <Badge size="xs" variant="light" color="green">
            local
          </Badge>
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

      <Group align="flex-end" wrap="nowrap">
        <FileButton onChange={adjuntar} accept="image/*,video/*,audio/*">
          {(props) => (
            <Button {...props} variant="default" px="sm" disabled={enviando}>
              <IconPaperclip size={18} />
            </Button>
          )}
        </FileButton>
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
  );
}
