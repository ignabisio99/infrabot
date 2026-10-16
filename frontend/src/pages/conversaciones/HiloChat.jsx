import { Paper, Stack, Text } from '@mantine/core';

import { formatoHoraMensaje } from '../../utils/formatters';

function urlMedia(path) {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  const origen = import.meta.env.VITE_API_URL || '';
  return `${origen}${path}`;
}

function textoSistema(msg) {
  const texto = msg.texto || '';
  const nombre = msg.operador_nombre;
  if (nombre && /^Admin\b/.test(texto) && !texto.startsWith(nombre)) {
    return texto.replace(/^Admin\b/, nombre);
  }
  return texto;
}

function colorAutor(autor) {
  if (autor === 'OPERADOR') return '#1fa7b3';
  if (autor === 'USUARIO') return '#132a4d';
  if (autor === 'SISTEMA') return 'transparent';
  return '#5c6b7a';
}

function MediaMensaje({ msg }) {
  if (msg.media_eliminada || !msg.media_url) {
    if (msg.tipo === 'AUDIO') {
      return (
        <Text size="sm" c="dimmed">
          Audio expirado
          {msg.transcripcion ? `: ${msg.transcripcion}` : ''}
        </Text>
      );
    }
    if (msg.tipo === 'IMAGEN' || msg.tipo === 'VIDEO') {
      return (
        <Text size="sm" c="dimmed">
          Archivo expirado{msg.texto ? ` — ${msg.texto}` : ''}
        </Text>
      );
    }
    return null;
  }
  if (msg.tipo === 'IMAGEN') {
    return (
      <Stack gap={4}>
        <img
          src={urlMedia(msg.media_url)}
          alt={msg.texto || 'imagen'}
          style={{ maxWidth: 280, borderRadius: 8 }}
        />
        {msg.texto ? (
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {msg.texto}
          </Text>
        ) : null}
      </Stack>
    );
  }
  if (msg.tipo === 'VIDEO') {
    return (
      <Stack gap={4}>
        <video src={urlMedia(msg.media_url)} controls style={{ maxWidth: 320, borderRadius: 8 }} />
        {msg.texto ? (
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {msg.texto}
          </Text>
        ) : null}
      </Stack>
    );
  }
  if (msg.tipo === 'AUDIO') {
    return (
      <Stack gap={4}>
        <audio src={urlMedia(msg.media_url)} controls />
        <Text size="xs" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
          {msg.transcripcion || 'Transcribiendo…'}
        </Text>
      </Stack>
    );
  }
  return null;
}

export function HiloChat({ mensajes, encabezado, pie }) {
  return (
    <Stack gap="sm" p={6} style={{ display: 'flex', flexDirection: 'column' }}>
      {encabezado}
      {mensajes.map((msg) => (
        <Paper
          key={msg.id}
          p="xs"
          radius="md"
          maw="80%"
          style={{
            alignSelf:
              msg.autor === 'OPERADOR' || msg.autor === 'BOT'
                ? 'flex-end'
                : msg.autor === 'SISTEMA'
                  ? 'center'
                  : 'flex-start',
            background: colorAutor(msg.autor),
            color: msg.autor === 'SISTEMA' ? undefined : 'white',
          }}
        >
          {msg.autor === 'SISTEMA' ? (
            <Text size="xs" c="dimmed" ta="center">
              {textoSistema(msg)}
              {formatoHoraMensaje(msg.fecha) ? ` · ${formatoHoraMensaje(msg.fecha)}` : ''}
            </Text>
          ) : (
            <>
              {msg.tipo === 'TEXTO' ? (
                <Text size="md" style={{ whiteSpace: 'pre-wrap' }}>
                  {msg.texto}
                </Text>
              ) : (
                <MediaMensaje msg={msg} />
              )}
              <Text size="xs" opacity={0.7} mt={4}>
                {msg.autor === 'OPERADOR'
                  ? msg.operador_nombre || 'Operador'
                  : msg.autor === 'BOT'
                    ? 'Bot'
                    : 'Usuario'}
                {formatoHoraMensaje(msg.fecha) ? ` · ${formatoHoraMensaje(msg.fecha)}` : ''}
              </Text>
            </>
          )}
        </Paper>
      ))}
      {pie}
    </Stack>
  );
}
