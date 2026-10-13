import { useEffect, useState } from 'react';
import {
  Accordion,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Textarea,
} from '@mantine/core';

import { crearComentarioReclamo, listarComentariosReclamo } from '../../api/reclamos';
import { notifyError } from '../../utils/notifications';

function etiquetaAutorComentario(comentario) {
  if (comentario.autor) return comentario.autor;
  const texto = comentario.texto || '';
  const whatsapp = /\[WhatsApp — ([^\]]+)\]/.exec(texto);
  if (whatsapp) return `${whatsapp[1]} (WhatsApp)`;
  if (texto.startsWith('[Sistema]') || texto.includes('Pendiente de intervención')) {
    return 'Sistema';
  }
  return 'Usuario eliminado';
}

function textoVisibleComentario(texto) {
  return (texto || '')
    .replace(/\[CU-05\]\s*/g, '')
    .replace(/^\[Sistema\]\s*/i, '')
    .trim();
}

export function ClaimCommentsThread({
  reclamoId,
  comentarios,
  puedeComentar = false,
  onComentarioAgregado,
}) {
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);

  const handleEnviar = async () => {
    setEnviando(true);
    try {
      const nuevo = await crearComentarioReclamo(reclamoId, texto);
      onComentarioAgregado?.(nuevo);
      setTexto('');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Stack gap="sm">
      {comentarios.length === 0 ? (
        <Text c="dimmed" size="sm">
          Ningún inspector comentó este reclamo.
        </Text>
      ) : (
        comentarios.map((comentario) => (
          <Paper key={comentario.id} withBorder radius="md" p="sm">
            <Group justify="space-between" mb={4}>
              <Text size="sm" fw={600}>
                {etiquetaAutorComentario(comentario)}
              </Text>
              <Text size="xs" c="dimmed">
                {new Date(comentario.fecha).toLocaleString('es-AR')}
              </Text>
            </Group>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {textoVisibleComentario(comentario.texto)}
            </Text>
          </Paper>
        ))
      )}

      {puedeComentar && (
        <>
          <Textarea
            placeholder="Escribí tu comentario sobre el reclamo..."
            minRows={3}
            autosize
            value={texto}
            onChange={(e) => setTexto(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button onClick={handleEnviar} loading={enviando} disabled={texto.trim() === ''}>
              Agregar comentario
            </Button>
          </Group>
        </>
      )}
    </Stack>
  );
}

/** Comentarios en sólo lectura dentro de un accordion cerrado, para los formularios de presupuesto. */
export function ClaimComments({ reclamoId }) {
  // Guarda a qué reclamo corresponde la lista: al cambiar de reclamo no se muestran los
  // comentarios del anterior mientras llegan los nuevos.
  const [cargados, setCargados] = useState({ reclamoId: null, lista: [] });

  useEffect(() => {
    let vigente = true;
    listarComentariosReclamo(reclamoId)
      .then((lista) => {
        if (vigente) setCargados({ reclamoId, lista });
      })
      .catch((err) => {
        if (vigente) {
          setCargados({ reclamoId, lista: [] });
          notifyError(err.message);
        }
      });
    return () => {
      vigente = false;
    };
  }, [reclamoId]);

  if (cargados.reclamoId !== reclamoId) return <Loader size="sm" />;
  const comentarios = cargados.lista;

  return (
    <Accordion variant="contained" radius="md">
      <Accordion.Item value="comentarios">
        <Accordion.Control>
          <Group gap="xs">
            <Text fw={600} size="sm">
              Comentarios de inspectores
            </Text>
            <Badge size="sm" variant="light" color={comentarios.length > 0 ? 'teal' : 'gray'}>
              {comentarios.length}
            </Badge>
          </Group>
        </Accordion.Control>
        <Accordion.Panel>
          <ClaimCommentsThread reclamoId={reclamoId} comentarios={comentarios} />
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
