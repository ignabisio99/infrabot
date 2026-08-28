import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  MultiSelect,
  SegmentedControl,
  Select,
  Stack,
  Text,
} from '@mantine/core';
import { IconBrandWhatsapp } from '@tabler/icons-react';

import { listarContratistas } from '../../api/contratistas';
import { listarListas, notificarContratistas } from '../../api/listasContratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function NotifyContractorsModal({ reclamoId, opened, onClose }) {
  const [modo, setModo] = useState('seleccion'); // 'seleccion' | 'lista'
  const [contratistas, setContratistas] = useState([]);
  const [listas, setListas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [seleccionados, setSeleccionados] = useState([]);
  const [listaElegida, setListaElegida] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!opened) return;
    setCargando(true);
    setErrorCarga(null);
    Promise.all([listarContratistas(), listarListas()])
      .then(([contratistasData, listasData]) => {
        setContratistas(contratistasData);
        setListas(listasData);
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [opened]);

  const opcionesContratistas = contratistas.map((c) => ({
    value: String(c.id),
    label: `${c.nombre_empresa} (${c.especialidad})`,
  }));

  const opcionesListas = listas.map((l) => ({
    value: String(l.id),
    label: `${l.nombre} (${l.contratistas.length} contratistas)`,
  }));

  const puedeEnviar =
    modo === 'seleccion' ? seleccionados.length > 0 : listaElegida !== '';

  const handleEnviar = async () => {
    setEnviando(true);
    try {
      const payload =
        modo === 'seleccion'
          ? { contratistaIds: seleccionados.map(Number) }
          : { listaId: Number(listaElegida) };

      const resultado = await notificarContratistas(reclamoId, payload);
      notifySuccess(
        `Notificación enviada a ${resultado.enviados} de ${resultado.total} contratista(s).`,
      );
      if (resultado.enviados < resultado.total) {
        const fallidos = resultado.resultados
          .filter((r) => !r.enviado)
          .map((r) => r.nombre_empresa)
          .join(', ');
        notifyError(`No se pudo notificar a: ${fallidos}`);
      }
      setSeleccionados([]);
      setListaElegida('');
      onClose();
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Notificar contratistas para presupuestar"
      size="lg"
      centered
    >
      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudieron cargar los datos">
          {errorCarga}
        </Alert>
      )}

      {!cargando && !errorCarga && (
        <Stack>
          <Text size="sm" c="dimmed">
            Se enviará un mensaje de WhatsApp a los contratistas seleccionados invitándolos a
            cargar su presupuesto para este reclamo.
          </Text>

          <SegmentedControl
            value={modo}
            onChange={setModo}
            data={[
              { label: 'Seleccionar contratistas', value: 'seleccion' },
              { label: 'Usar una lista', value: 'lista' },
            ]}
            fullWidth
          />

          {modo === 'seleccion' ? (
            <MultiSelect
              label="Contratistas"
              placeholder="Elegí uno o varios"
              data={opcionesContratistas}
              value={seleccionados}
              onChange={setSeleccionados}
              searchable
              nothingFoundMessage="No hay contratistas"
            />
          ) : (
            <Select
              label="Lista predefinida"
              placeholder="Elegí una lista"
              data={opcionesListas}
              value={listaElegida}
              onChange={(v) => setListaElegida(v || '')}
              searchable
              nothingFoundMessage="No hay listas creadas"
            />
          )}

          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              leftSection={<IconBrandWhatsapp size={18} />}
              color="teal"
              onClick={handleEnviar}
              loading={enviando}
              disabled={!puedeEnviar}
            >
              Enviar notificación
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
