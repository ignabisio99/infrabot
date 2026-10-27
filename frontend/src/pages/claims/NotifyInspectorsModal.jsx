import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Stack,
  Text,
  Textarea,
} from '@mantine/core';
import { IconSend } from '@tabler/icons-react';

import { notificarInspectores } from '../../api/reclamos';
import { listarInspectores } from '../../api/usuarios';
import { notifyError, notifySuccess } from '../../utils/notifications';

/** Resume a quién no le llegó por algún canal, para que el admin sepa si tiene que avisar a mano. */
function avisoCanalesFallidos(resultados) {
  const sinWhatsapp = resultados.filter((r) => !r.whatsapp).map((r) => r.nombre);
  const sinEmail = resultados.filter((r) => !r.email).map((r) => r.nombre);
  const partes = [];
  if (sinWhatsapp.length) partes.push(`no les llegó por WhatsApp: ${sinWhatsapp.join(', ')}`);
  if (sinEmail.length) partes.push(`no les llegó por email: ${sinEmail.join(', ')}`);
  return partes.length ? `Lo van a ver igual al entrar a la app, pero ${partes.join('; ')}.` : null;
}

export function NotifyInspectorsModal({ reclamoId, opened, onClose, onEnviado }) {
  const [inspectores, setInspectores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [seleccionados, setSeleccionados] = useState([]);
  const [mensaje, setMensaje] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!opened) return;
    let vigente = true;
    listarInspectores()
      .then((data) => {
        if (vigente) setInspectores(data);
      })
      .catch((err) => {
        if (vigente) setErrorCarga(err.message);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [opened]);

  const opciones = inspectores.map((i) => ({
    value: String(i.id),
    label: i.telefono ? i.nombre : `${i.nombre} (sin WhatsApp cargado)`,
  }));

  const cerrar = () => {
    setSeleccionados([]);
    setMensaje('');
    onClose();
  };

  const handleEnviar = async () => {
    setEnviando(true);
    try {
      const resultado = await notificarInspectores(reclamoId, {
        inspectorIds: seleccionados.map(Number),
        mensaje: mensaje.trim(),
      });
      notifySuccess(
        resultado.total === 1
          ? `Le pediste información a ${resultado.resultados[0].nombre}.`
          : `Le pediste información a ${resultado.total} inspectores.`,
      );
      const aviso = avisoCanalesFallidos(resultado.resultados);
      if (aviso) notifyError(aviso);
      onEnviado?.();
      cerrar();
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={cerrar}
      title="Pedir información a inspectores"
      size="lg"
      centered
    >
      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudieron cargar los inspectores">
          {errorCarga}
        </Alert>
      )}

      {!cargando && !errorCarga && (
        <Stack>
          <Text size="sm" c="dimmed">
            Les llega por WhatsApp y por email, y les aparece al entrar a la app hasta que agreguen
            un comentario o una foto en este reclamo.
          </Text>

          <MultiSelect
            label="Inspectores"
            placeholder="Elegí uno o varios"
            data={opciones}
            value={seleccionados}
            onChange={setSeleccionados}
            searchable
            nothingFoundMessage="No hay inspectores aprobados"
          />

          <Textarea
            label="¿Qué información necesitás? (opcional)"
            placeholder="Ej: fotos del tablero eléctrico y medidas del aula"
            value={mensaje}
            onChange={(e) => setMensaje(e.currentTarget.value)}
            maxLength={1000}
            autosize
            minRows={3}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={cerrar}>
              Cancelar
            </Button>
            <Button
              leftSection={<IconSend size={18} />}
              onClick={handleEnviar}
              loading={enviando}
              disabled={seleccionados.length === 0}
            >
              Enviar pedido
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
