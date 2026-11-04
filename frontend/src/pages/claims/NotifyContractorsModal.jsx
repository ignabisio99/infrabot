import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Flex,
  Group,
  List,
  Loader,
  Modal,
  Paper,
  Rating,
  ScrollArea,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconAlertTriangle, IconBrandWhatsapp, IconSearch, IconStarFilled } from '@tabler/icons-react';

import { listarContratistas } from '../../api/contratistas';
import {
  ContratistasYaNotificadosError,
  listarListas,
  notificarContratistas,
} from '../../api/listasContratistas';
import { useEsMobile } from '../../hooks/useEsMobile';
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

// Qué tan confiable es el contratista según su calificación (1 a 5, o sin calificar).
function nivelCalificacion(calificacion) {
  if (calificacion == null) return { etiqueta: 'Sin calificar', color: 'gray' };
  if (calificacion >= 5) return { etiqueta: 'Excelente', color: 'teal' };
  if (calificacion >= 4) return { etiqueta: 'Buena', color: 'teal' };
  if (calificacion >= 3) return { etiqueta: 'Regular', color: 'yellow' };
  if (calificacion >= 2) return { etiqueta: 'Mala', color: 'red' };
  return { etiqueta: 'Muy mala', color: 'red' };
}

const normalizar = (texto) =>
  (texto || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

// La especialidad "coincide" con la categoría del reclamo si una contiene a la otra
// (sin acentos ni mayúsculas), o si el contratista hace de todo.
function coincideEspecialidad(especialidad, categoria) {
  const e = normalizar(especialidad);
  const c = normalizar(categoria);
  if (!e || !c) return false;
  if (['todo', 'general', 'todos'].includes(e)) return true;
  return e.includes(c) || c.includes(e);
}

const ORDENES = [
  { value: 'recomendados', label: 'Recomendados' },
  { value: 'calificacion', label: 'Mejor calificación' },
  { value: 'nombre', label: 'Nombre (A-Z)' },
];

const porCalificacion = (a, b) => (b.calificacion ?? -1) - (a.calificacion ?? -1);
const porNombre = (a, b) => a.nombre_empresa.localeCompare(b.nombre_empresa, 'es');

function CalificacionContratista({ calificacion }) {
  const nivel = nivelCalificacion(calificacion);
  return (
    <Stack gap={2} align="flex-end" style={{ flex: 'none' }}>
      <Rating value={calificacion ?? 0} readOnly size="sm" color="yellow" />
      <Badge size="xs" variant="light" color={nivel.color} tt="none">
        {calificacion != null ? `${calificacion}/5 · ${nivel.etiqueta}` : nivel.etiqueta}
      </Badge>
    </Stack>
  );
}

function DatosContratista({ contratista, categoria }) {
  const coincide = coincideEspecialidad(contratista.especialidad, categoria);
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <Text fw={600} size="sm" truncate>
        {contratista.nombre_empresa}
      </Text>
      <Group gap={6} mt={2}>
        <Badge size="xs" variant="light" color="gray" tt="none">
          {contratista.especialidad}
        </Badge>
        {coincide && (
          <Badge size="xs" variant="light" color="teal" tt="none" leftSection={<IconStarFilled size={9} />}>
            Coincide con el reclamo
          </Badge>
        )}
      </Group>
      {contratista.observaciones_calificacion && (
        <Text size="xs" c="dimmed" mt={4} lineClamp={2}>
          {contratista.observaciones_calificacion}
        </Text>
      )}
    </div>
  );
}

export function NotifyContractorsModal({ reclamoId, categoria, opened, onClose }) {
  const esMobile = useEsMobile();
  const [modo, setModo] = useState('seleccion'); // 'seleccion' | 'lista'
  const [contratistas, setContratistas] = useState([]);
  const [listas, setListas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [seleccionados, setSeleccionados] = useState([]);
  const [listaElegida, setListaElegida] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [orden, setOrden] = useState(categoria ? 'recomendados' : 'calificacion');
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

  // Los dados de baja no se notifican (el backend los omite), así que no se ofrecen.
  const activos = useMemo(() => contratistas.filter((c) => !c.fecha_baja), [contratistas]);

  const visibles = useMemo(() => {
    const termino = normalizar(busqueda);
    const filtrados = activos.filter(
      (c) =>
        !termino ||
        normalizar(c.nombre_empresa).includes(termino) ||
        normalizar(c.especialidad).includes(termino),
    );
    const copia = [...filtrados];
    if (orden === 'nombre') return copia.sort(porNombre);
    if (orden === 'calificacion') return copia.sort((a, b) => porCalificacion(a, b) || porNombre(a, b));
    // Recomendados: primero los de la especialidad del reclamo, después por calificación.
    return copia.sort((a, b) => {
      const ca = coincideEspecialidad(a.especialidad, categoria) ? 1 : 0;
      const cb = coincideEspecialidad(b.especialidad, categoria) ? 1 : 0;
      return cb - ca || porCalificacion(a, b) || porNombre(a, b);
    });
  }, [activos, busqueda, orden, categoria]);

  const alternar = (id) =>
    setSeleccionados((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );

  // Los dados de baja siguen en la lista, pero el backend no los notifica.
  const activosDe = (lista) => lista.contratistas.filter((c) => !c.fecha_baja);

  const opcionesListas = listas.map((l) => ({
    value: String(l.id),
    label: `${l.nombre} (${activosDe(l).length} contratistas)`,
  }));

  const listaSeleccionada = listas.find((l) => String(l.id) === listaElegida);

  const puedeEnviar = modo === 'seleccion' ? seleccionados.length > 0 : listaElegida !== '';

  const cantidadDestinatarios =
    modo === 'seleccion'
      ? seleccionados.length
      : activosDe(listaSeleccionada ?? { contratistas: [] }).length;
  const cantidadNuevos = cantidadDestinatarios - (yaNotificados?.length ?? 0);

  const cerrar = () => {
    setSeleccionados([]);
    setListaElegida('');
    setBusqueda('');
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
      title={
        <Text fw={700} size="lg">
          Solicitar presupuesto
        </Text>
      }
      size="lg"
      fullScreen={esMobile}
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
            Los contratistas elegidos reciben un WhatsApp y un mail para cargar su presupuesto.
            Revisá la calificación de cada uno antes de elegir.
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
            <Stack gap="xs">
              <Flex gap="sm" direction={{ base: 'column', xs: 'row' }}>
                <TextInput
                  placeholder="Buscar por nombre o especialidad"
                  aria-label="Buscar contratista"
                  leftSection={<IconSearch size={16} />}
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <Select
                  aria-label="Ordenar contratistas"
                  data={categoria ? ORDENES : ORDENES.filter((o) => o.value !== 'recomendados')}
                  value={orden}
                  onChange={(v) => setOrden(v || 'calificacion')}
                  allowDeselect={false}
                  w={{ base: '100%', xs: 190 }}
                />
              </Flex>

              <Flex justify="space-between" align="center">
                <Text size="sm" c="dimmed">
                  {seleccionados.length === 0
                    ? `${visibles.length} contratista(s) disponibles`
                    : `${seleccionados.length} seleccionado(s)`}
                </Text>
                {seleccionados.length > 0 && (
                  <Button variant="subtle" size="compact-xs" onClick={() => setSeleccionados([])}>
                    Quitar selección
                  </Button>
                )}
              </Flex>

              <ScrollArea.Autosize mah={esMobile ? undefined : 380} offsetScrollbars type="auto">
                <Stack gap="xs">
                  {visibles.length === 0 && (
                    <Text size="sm" c="dimmed" ta="center" py="md">
                      No hay contratistas que coincidan con la búsqueda.
                    </Text>
                  )}
                  {visibles.map((c) => {
                    const elegido = seleccionados.includes(String(c.id));
                    return (
                      <Checkbox.Card
                        key={c.id}
                        checked={elegido}
                        onClick={() => alternar(String(c.id))}
                        radius="md"
                        p="sm"
                        style={{
                          borderColor: elegido ? 'var(--mantine-color-teal-6)' : undefined,
                          backgroundColor: elegido ? 'var(--mantine-color-teal-0)' : undefined,
                        }}
                      >
                        <Flex gap="sm" align="flex-start" wrap="nowrap">
                          <Checkbox.Indicator color="teal" mt={2} />
                          <DatosContratista contratista={c} categoria={categoria} />
                          <CalificacionContratista calificacion={c.calificacion} />
                        </Flex>
                      </Checkbox.Card>
                    );
                  })}
                </Stack>
              </ScrollArea.Autosize>
            </Stack>
          ) : (
            <Stack gap="xs">
              <Select
                label="Lista predefinida"
                placeholder="Elegí una lista"
                data={opcionesListas}
                value={listaElegida}
                onChange={(v) => setListaElegida(v || '')}
                searchable
                nothingFoundMessage="No hay listas creadas"
              />
              {listaSeleccionada && (
                <>
                  <Text size="sm" c="dimmed">
                    Se va a notificar a:
                  </Text>
                  <ScrollArea.Autosize mah={esMobile ? undefined : 320} offsetScrollbars type="auto">
                    <Stack gap="xs">
                      {activosDe(listaSeleccionada)
                        .slice()
                        .sort((a, b) => porCalificacion(a, b) || porNombre(a, b))
                        .map((c) => (
                          <Paper key={c.id} withBorder radius="md" p="sm">
                            <Flex gap="sm" align="flex-start" wrap="nowrap">
                              <DatosContratista contratista={c} categoria={categoria} />
                              <CalificacionContratista calificacion={c.calificacion} />
                            </Flex>
                          </Paper>
                        ))}
                    </Stack>
                  </ScrollArea.Autosize>
                </>
              )}
            </Stack>
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
