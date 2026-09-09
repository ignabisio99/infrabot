import { useState } from 'react';
import { Alert, Button, Group, Modal, Select, Stack, Text, Textarea } from '@mantine/core';
import { IconMessagePlus } from '@tabler/icons-react';

import { notifyError, notifySuccess } from '../utils/notifications';

// Compartido por reclamos y presupuestos: las dos entidades tienen máquina de estados
// con historial y motivo obligatorio en algunos destinos. Lo que cambia son los textos y
// los colores, y va en `config` (ver pages/*/estados.js).
//
// `entidad` trae `estados_posibles`, que es lo que el backend habilita desde el estado
// actual: el select nunca ofrece una transición que después vaya a fallar.
export function ChangeStateModal({ entidad, config, onSubmit, onClose, onCambiado }) {
  const [estado, setEstado] = useState(null);
  const [motivo, setMotivo] = useState('');
  const [motivoTocado, setMotivoTocado] = useState(false);
  const [mostrarComentario, setMostrarComentario] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const abierto = entidad !== null;

  // Al abrir el modal para otra entidad hay que limpiar el formulario. Se hace
  // comparando contra el id previo en el render (y no con un efecto) para no
  // disparar un render en cascada.
  const [idPrevio, setIdPrevio] = useState(null);
  const idActual = entidad?.id ?? null;
  if (idActual !== idPrevio) {
    setIdPrevio(idActual);
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

  const motivoObligatorio = estado !== null && config.requiereMotivo(estado);
  const motivoFaltante = motivoObligatorio && motivo.trim() === '';
  const textoMotivo = config.textoMotivoPorEstado[estado];
  // Para los destinos que arrastran cosas fuera de la entidad: conviene decirlo antes
  // de guardar, no después.
  const aviso = config.avisoPorEstado?.[estado];
  const Badge = config.Badge;

  const handleGuardar = async () => {
    setGuardando(true);
    try {
      const actualizada = await onSubmit(entidad.id, estado, motivo);
      notifySuccess(config.mensajeExito(config.etiquetaPorEstado[estado]));
      onCambiado(actualizada);
      onClose();
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Modal opened={abierto} onClose={onClose} title={config.titulo} centered>
      {entidad && (
        <Stack>
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              Estado actual:
            </Text>
            <Badge estado={entidad.estado} variant="light" />
          </Group>

          {entidad.estados_posibles.length === 0 ? (
            <Alert color="gray">{config.textoSinTransiciones}</Alert>
          ) : (
            <>
              <Select
                label={config.labelNuevoEstado}
                placeholder="Elegí el estado"
                data={entidad.estados_posibles.map((valor) => ({
                  value: valor,
                  label: config.etiquetaPorEstado[valor],
                }))}
                value={estado}
                onChange={setEstado}
                allowDeselect={false}
              />

              {aviso && (
                <Alert color="blue" variant="light">
                  {aviso}
                </Alert>
              )}

              {/* El campo sólo aparece una vez elegido el destino: hasta ahí no se
                  sabe si corresponde un motivo obligatorio o un comentario opcional. */}
              {motivoObligatorio && (
                <Textarea
                  label={textoMotivo.label}
                  description={config.descripcionMotivo}
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
                    description={`Opcional. ${config.descripcionMotivo}`}
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
                  {config.etiquetaSubmit}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      )}
    </Modal>
  );
}
