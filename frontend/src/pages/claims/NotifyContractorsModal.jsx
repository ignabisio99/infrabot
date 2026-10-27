import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Group,
  List,
  Loader,
  Modal,
  MultiSelect,
  SegmentedControl,
  Select,
  Stack,
  Text,
} from '@mantine/core';
import { IconAlertTriangle, IconBrandWhatsapp } from '@tabler/icons-react';

import { listarContratistas } from '../../api/contratistas';
import {
  ContratistasYaNotificadosError,
  listarListas,
  notificarContratistas,
} from '../../api/listasContratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

function cuandoSeNotifico(fecha) {
  const minutos = Math.floor((Date.now() - new Date(fecha).getTime()) / 60000);
  if (minutos < 1) return 'recién';
  if (minutos < 60) return `hace ${minutos} min`;
  if (minutos < 24 * 60) return `hace ${Math.floor(minutos / 60)} h`;
  const dia = new Date(fecha).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return `el ${dia}`;
}

export function NotifyContractorsModal({ reclamoId, opened, onClose }) {
  const [modo, setModo] = useState('seleccion'); // 'seleccion' | 'lista'
  const [contratistas, setContratistas] = useState([]);
  const [listas, setListas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [seleccionados, setSeleccionados] = useState([]);
  const [listaElegida, setListaElegida] = useState('');
  // Con qué opción se está enviando ('preguntar' | 'reenviar' | 'omitir'), o null.
  const [enviando, setEnviando] = useState(null);
  // Los que el backend avisó que ya estaban notificados: mientras no sea null se pide
  // confirmación en vez de mostrar el formulario.
  const [yaNotificados, setYaNotificados] = useState(null);

  useEffect(() => {
    if (!opened) return;
    let vigente = true;
    Promise.all([listarContratistas(), listarListas()])
      .then(([contratistasData, listasData]) => {
        if (!vigente) return;
        setContratistas(contratistasData);
        setListas(listasData);
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

  const opcionesContratistas = contratistas.map((c) => ({
    value: String(c.id),
    label: `${c.nombre_empresa} (${c.especialidad})`,
  }));

  const opcionesListas = listas.map((l) => ({
    value: String(l.id),
    label: `${l.nombre} (${l.contratistas.length} contratistas)`,
  }));

  const puedeEnviar = modo === 'seleccion' ? seleccionados.length > 0 : listaElegida !== '';

  const cantidadDestinatarios =
    modo === 'seleccion'
      ? seleccionados.length
      : (listas.find((l) => String(l.id) === listaElegida)?.contratistas.length ?? 0);
  const cantidadNuevos = cantidadDestinatarios - (yaNotificados?.length ?? 0);

  const cerrar = () => {
    setSeleccionados([]);
    setListaElegida('');
    setYaNotificados(null);
    setErrorCarga(null);
    onClose();
  };

  const enviar = async (siYaNotificados) => {
    setEnviando(siYaNotificados);
    try {
      const destinatarios =
        modo === 'seleccion'
          ? { contratistaIds: seleccionados.map(Number) }
          : { listaId: Number(listaElegida) };

      const resultado = await notificarContratistas(reclamoId, {
        ...destinatarios,
        yaNotificados: siYaNotificados,
      });
      const omitidos = siYaNotificados === 'omitir' ? yaNotificados.length : 0;
      const aclaracion =
        omitidos === 1
          ? ' No se reenvió al que ya estaba notificado.'
          : omitidos > 1
            ? ` No se reenvió a los ${omitidos} que ya estaban notificados.`
            : '';
      if (resultado.enviados > 0) {
        notifySuccess(
          `Notificación enviada a ${resultado.enviados} de ${resultado.total} contratista(s).${aclaracion}`,
        );
      }
      if (resultado.enviados < resultado.total) {
        const fallidos = resultado.resultados
          .filter((r) => !r.enviado)
          .map((r) => r.nombre_empresa)
          .join(', ');
        notifyError(`No se pudo notificar a: ${fallidos}`);
      }
      cerrar();
    } catch (error) {
      if (error instanceof ContratistasYaNotificadosError) {
        setYaNotificados(error.yaNotificados);
      } else {
        notifyError(error?.message);
      }
    } finally {
      setEnviando(null);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={cerrar}
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

      {!cargando && !errorCarga && yaNotificados && (
        <Stack>
          <Alert
            color="yellow"
            icon={<IconAlertTriangle size={18} />}
            title={
              yaNotificados.length === 1
                ? 'Este contratista ya fue notificado para este reclamo'
                : 'Estos contratistas ya fueron notificados para este reclamo'
            }
          >
            <List size="sm">
              {yaNotificados.map((c) => (
                <List.Item key={c.contratista_id}>
                  <Text span size="sm" fw={600}>
                    {c.nombre_empresa}
                  </Text>
                  : {cuandoSeNotifico(c.fecha_ultimo_aviso)}
                  {c.presupuesto_cargado && ' (ya mandó una oferta)'}
                </List.Item>
              ))}
            </List>
          </Alert>

          <Text size="sm">
            {yaNotificados.length === 1
              ? '¿Querés volver a notificarlo?'
              : '¿Querés volver a notificarlos?'}
          </Text>

          <Group justify="flex-end">
            <Button variant="default" onClick={() => setYaNotificados(null)} disabled={!!enviando}>
              Cancelar
            </Button>
            {cantidadNuevos > 0 && (
              <Button
                variant="light"
                color="teal"
                onClick={() => enviar('omitir')}
                loading={enviando === 'omitir'}
                disabled={!!enviando}
              >
                Solo a los nuevos ({cantidadNuevos})
              </Button>
            )}
            <Button
              leftSection={<IconBrandWhatsapp size={18} />}
              color="teal"
              onClick={() => enviar('reenviar')}
              loading={enviando === 'reenviar'}
              disabled={!!enviando}
            >
              {cantidadNuevos > 0 ? 'Reenviar a todos' : 'Reenviar'}
            </Button>
          </Group>
        </Stack>
      )}

      {!cargando && !errorCarga && !yaNotificados && (
        <Stack>
          <Text size="sm" c="dimmed">
            Se enviará un mensaje de WhatsApp a los contratistas seleccionados invitándolos a cargar
            su presupuesto para este reclamo.
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
            <Button variant="default" onClick={cerrar}>
              Cancelar
            </Button>
            <Button
              leftSection={<IconBrandWhatsapp size={18} />}
              color="teal"
              onClick={() => enviar('preguntar')}
              loading={enviando === 'preguntar'}
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
