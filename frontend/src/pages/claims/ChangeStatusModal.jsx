import { useState } from 'react';
import { Alert, Button, Group, Modal, Select, Stack, Text, Textarea } from '@mantine/core';
import { IconMessagePlus } from '@tabler/icons-react';

import { cambiarEstadoReclamo } from '../../api/reclamos';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { StatusBadge } from './StatusBadge';
import { etiquetaPorEstado, requiereMotivo, textoMotivoPorEstado } from './estados';

// `reclamo` trae `estados_posibles`, que es lo que el backend habilita desde el
// estado actual: el select nunca ofrece una transición que después vaya a fallar.
export function ChangeStatusModal({ reclamo, onClose, onEstadoCambiado }) {
  const [estado, setEstado] = useState(null);
  const [motivo, setMotivo] = useState('');
  const [motivoTocado, setMotivoTocado] = useState(false);
  const [mostrarComentario, setMostrarComentario] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const abierto = reclamo !== null;

  // Al abrir el modal para otro reclamo hay que limpiar el formulario. Se hace
  // comparando contra el id previo en el render (y no con un efecto) para no
  // disparar un render en cascada.
  const [reclamoIdPrevio, setReclamoIdPrevio] = useState(null);
  const reclamoIdActual = reclamo?.id ?? null;
  if (reclamoIdActual !== reclamoIdPrevio) {
    setReclamoIdPrevio(reclamoIdActual);
    setEstado(null);
  }

  // Cambiar el estado destino cambia el sentido del campo de texto (motivo obligatorio
  // vs comentario opcional), así que se descarta lo escrito para el estado anterior.
  const [estadoPrevio, setEstadoPrevio] = useState(null);
  if (estado !== estadoPrevio) {
    setEstadoPrevio(estado);
    setMotivo('');
    setMotivoTocado(false);
    setMostrarComentario(false);
  }

  const motivoObligatorio = estado !== null && requiereMotivo(estado);
  const motivoFaltante = motivoObligatorio && motivo.trim() === '';
  const textoMotivo = textoMotivoPorEstado[estado];

  const handleGuardar = async () => {
    setGuardando(true);
    try {
      const actualizado = await cambiarEstadoReclamo(reclamo.id, estado, motivo);
      notifySuccess(`El reclamo pasó a "${etiquetaPorEstado[estado]}".`);
      onEstadoCambiado(actualizado);
      onClose();
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Modal opened={abierto} onClose={onClose} title="Cambiar estado del reclamo" centered>
      {reclamo && (
        <Stack>
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              Estado actual:
            </Text>
            <StatusBadge estado={reclamo.estado} variant="light" />
          </Group>

          {reclamo.estados_posibles.length === 0 ? (
            <Alert color="gray">Este reclamo está en un estado final y ya no puede cambiar.</Alert>
          ) : (
            <>
              <Select
                label="Nuevo estado"
                placeholder="Elegí el estado"
                data={reclamo.estados_posibles.map((valor) => ({
                  value: valor,
                  label: etiquetaPorEstado[valor],
                }))}
                value={estado}
                onChange={setEstado}
                allowDeselect={false}
              />

              {/* El campo sólo aparece una vez elegido el destino: hasta ahí no se
                  sabe si corresponde un motivo obligatorio o un comentario opcional. */}
              {motivoObligatorio && (
                <Textarea
                  label={textoMotivo.label}
                  description="Queda registrado en el historial del reclamo."
                  placeholder={textoMotivo.placeholder}
                  value={motivo}
                  onChange={(event) => setMotivo(event.currentTarget.value)}
                  onBlur={() => setMotivoTocado(true)}
                  error={motivoTocado && motivoFaltante ? 'Indicá el motivo del cambio.' : null}
                  withAsterisk
                  autosize
                  minRows={2}
                />
              )}

              {estado !== null &&
                !motivoObligatorio &&
                (mostrarComentario ? (
                  <Textarea
                    label="Comentario"
                    description="Opcional. Queda registrado en el historial del reclamo."
                    value={motivo}
                    onChange={(event) => setMotivo(event.currentTarget.value)}
                    autosize
                    minRows={2}
                    data-autofocus
                  />
                ) : (
                  <Group justify="flex-start">
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      leftSection={<IconMessagePlus size={14} />}
                      onClick={() => setMostrarComentario(true)}
                    >
                      Agregar un comentario
                    </Button>
                  </Group>
                ))}

              <Group justify="flex-end">
                <Button variant="default" onClick={onClose}>
                  Cancelar
                </Button>
                <Button
                  onClick={handleGuardar}
                  loading={guardando}
                  disabled={estado === null || motivoFaltante}
                >
                  Cambiar estado
                </Button>
              </Group>
            </>
          )}
        </Stack>
      )}
    </Modal>
  );
}
