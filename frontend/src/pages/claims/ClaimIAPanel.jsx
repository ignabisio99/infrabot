import { useEffect, useState } from 'react';
import { Alert, Anchor, Badge, Button, Group, List, Paper, Stack, Text } from '@mantine/core';

import {
  analizarMediaReclamo,
  buscarDuplicados,
  clasificarReclamo,
  crearEstimacion,
  listarRecomendaciones,
  obtenerEstimacion,
  orquestarReclamo,
} from '../../api/ai';
import { formatoMoneda } from '../../utils/formatters';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { PriorityBadge } from './PriorityBadge';

function Bloque({ titulo, children }) {
  return (
    <Paper withBorder radius="md" p="sm">
      <Text fw={600} size="sm" mb="xs">
        {titulo}
      </Text>
      {children}
    </Paper>
  );
}

function parsePayload(payload) {
  try {
    return JSON.parse(payload);
  } catch {
    return {};
  }
}

function ultimaDeTipo(recomendaciones, tipo) {
  return recomendaciones.find((item) => item.tipo === tipo);
}

function leerDetalleEstimacion(detalle) {
  if (!detalle) return { sinPrecedencias: false, aviso: null };
  try {
    const parsed = typeof detalle === 'string' ? JSON.parse(detalle) : detalle;
    const motivo = parsed.validacion?.motivo;
    const refs = parsed.referencias_ids;
    const sinPrecedencias =
      motivo === 'sin_referencias' ||
      motivo === 'promedio_refs_invalido' ||
      (Array.isArray(refs) && refs.length === 0);
    let aviso = parsed.aviso || null;
    if (!aviso && sinPrecedencias) {
      aviso =
        'No hay datos históricos similares para basar esta estimación. Se recomienda inspección técnica presencial.';
    }
    if (!aviso && motivo === 'desvio_vs_historicos') {
      aviso = 'El total se aleja de los costos históricos similares.';
    }
    return { sinPrecedencias, aviso };
  } catch {
    return { sinPrecedencias: false, aviso: null };
  }
}

export function ClaimIAPanel({
  reclamo,
  soloLectura = false,
  onReclamoActualizado,
  onAbrirReclamo,
}) {
  const [clasificacion, setClasificacion] = useState(null);
  const [aplicando, setAplicando] = useState(false);

  const [duplicados, setDuplicados] = useState(null);
  const [buscandoDups, setBuscandoDups] = useState(true);

  const [estimacion, setEstimacion] = useState(null);
  const [cargandoEst, setCargandoEst] = useState(true);
  const [generandoEst, setGenerandoEst] = useState(false);

  const [vision, setVision] = useState(null);
  const [analizando, setAnalizando] = useState(false);
  const [orquestando, setOrquestando] = useState(false);
  const [pipeline, setPipeline] = useState(null);

  const [reclamoCargado, setReclamoCargado] = useState(reclamo.id);
  if (reclamoCargado !== reclamo.id) {
    setReclamoCargado(reclamo.id);
    setClasificacion(null);
    setDuplicados(null);
    setEstimacion(null);
    setVision(null);
    setPipeline(null);
    setCargandoEst(true);
    setBuscandoDups(true);
  }

  const hayFotos = (reclamo.fotos || []).some((foto) => foto.tipo === 'IMAGEN');
  const metaEstimacion = estimacion ? leerDetalleEstimacion(estimacion.detalle) : null;
  const sinPrecedencias = Boolean(estimacion?.sin_precedentes || metaEstimacion?.sinPrecedencias);
  const aviso = metaEstimacion?.aviso;

  useEffect(() => {
    let vigente = true;

    Promise.all([
      obtenerEstimacion(reclamo.id),
      buscarDuplicados(reclamo.id),
      listarRecomendaciones({ reclamoId: reclamo.id }),
    ])
      .then(([est, dups, recs]) => {
        if (!vigente) return;
        setEstimacion(est);
        setDuplicados(dups);
        const clasif = ultimaDeTipo(recs, 'CLASIFICACION');
        if (clasif) {
          const payload = parsePayload(clasif.payload);
          setClasificacion({
            categoria: payload.categoria || reclamo.categoria,
            prioridad: payload.prioridad || reclamo.prioridad,
            confianza: clasif.confianza ?? 0,
            justificacion: payload.justificacion || '',
            razonamiento: payload.razonamiento || '',
          });
        }
        const vis = ultimaDeTipo(recs, 'VISION');
        if (vis) {
          const payload = parsePayload(vis.payload);
          setVision({
            hallazgos: payload.hallazgos || [],
            severidad: payload.severidad || 'MEDIA',
            sugerencia_descripcion: payload.sugerencia_descripcion || '',
          });
        }
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      })
      .finally(() => {
        if (!vigente) return;
        setCargandoEst(false);
        setBuscandoDups(false);
      });

    return () => {
      vigente = false;
    };
  }, [reclamo.id, reclamo.categoria, reclamo.prioridad]);

  const aplicar = async () => {
    setAplicando(true);
    try {
      const resultado = await clasificarReclamo(reclamo.id, { aplicar: true });
      setClasificacion(resultado);
      notifySuccess('Se reaplicó la categoría y prioridad sugeridas.');
      onReclamoActualizado?.();
    } catch (err) {
      notifyError(err.message);
    } finally {
      setAplicando(false);
    }
  };

  const regenerarDuplicados = async () => {
    setBuscandoDups(true);
    try {
      const resultado = await buscarDuplicados(reclamo.id);
      setDuplicados(resultado);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setBuscandoDups(false);
    }
  };

  const generar = async () => {
    setGenerandoEst(true);
    try {
      const resultado = await crearEstimacion(reclamo.id);
      setEstimacion(resultado);
      notifySuccess('Estimación preliminar regenerada.');
      onReclamoActualizado?.();
    } catch (err) {
      notifyError(err.message);
    } finally {
      setGenerandoEst(false);
    }
  };

  const analizar = async () => {
    setAnalizando(true);
    try {
      const resultado = await analizarMediaReclamo(reclamo.id);
      setVision(resultado);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setAnalizando(false);
    }
  };

  const orquestar = async () => {
    setOrquestando(true);
    try {
      const resultado = await orquestarReclamo(reclamo.id);
      setPipeline(resultado);
      if (resultado.categoria) {
        setClasificacion({
          categoria: resultado.categoria,
          prioridad: resultado.prioridad,
          confianza: resultado.confianza,
          justificacion: resultado.justificacion,
          razonamiento: resultado.razonamiento || '',
        });
      }
      if (resultado.duplicados) {
        setDuplicados({ reclamo_id: reclamo.id, candidatos: resultado.duplicados });
      }
      const est = await obtenerEstimacion(reclamo.id);
      setEstimacion(est);
      notifySuccess('Se volvió a analizar el reclamo.');
      onReclamoActualizado?.();
    } catch (err) {
      notifyError(err.message);
    } finally {
      setOrquestando(false);
    }
  };

  return (
    <Stack gap="md">
      <Alert color="blue" title="Análisis automático">
        {soloLectura
          ? 'El reclamo está cerrado: acá quedan los últimos resultados de la IA, pero ya no se pueden regenerar.'
          : 'La IA corre sola al registrar el reclamo y al subir fotos. Acá se ven los resultados; los botones de abajo solo regeneran si hace falta.'}
      </Alert>

      {pipeline && (
        <Text size="sm" c="dimmed">
          Último recálculo: {(pipeline.pasos || []).join(' → ')}
        </Text>
      )}

      <Bloque titulo="Clasificación">
        <Text size="sm" c="dimmed" mb="xs">
          En el reclamo: {reclamo.categoria} ·{' '}
          <PriorityBadge prioridad={reclamo.prioridad} size="xs" />
        </Text>
        {clasificacion && (
          <Paper radius="sm" p="xs" mb="xs" bg="gray.0">
            <Group gap="xs" mb={4}>
              <Text size="sm" fw={500}>
                {clasificacion.categoria}
              </Text>
              <PriorityBadge prioridad={clasificacion.prioridad} size="xs" />
              <Badge
                size="xs"
                variant="light"
                color={Math.round((clasificacion.confianza || 0) * 100) < 50 ? 'yellow' : undefined}
              >
                {Math.round((clasificacion.confianza || 0) * 100)}%
              </Badge>
            </Group>
            {clasificacion.justificacion && <Text size="sm">{clasificacion.justificacion}</Text>}
            {clasificacion.razonamiento && (
              <Text size="xs" c="dimmed" mt={4} fs="italic">
                🧠 Razonamiento: {clasificacion.razonamiento}
              </Text>
            )}
          </Paper>
        )}
        <Button
          size="xs"
          variant="subtle"
          loading={aplicando}
          disabled={soloLectura}
          onClick={aplicar}
        >
          Reaplicar clasificación
        </Button>
      </Bloque>

      <Bloque titulo="Posibles duplicados">
        {buscandoDups && (
          <Text size="sm" c="dimmed" mb="xs">
            Buscando similares…
          </Text>
        )}
        {duplicados && duplicados.candidatos.length === 0 && (
          <Text size="sm" c="dimmed">
            No se encontraron reclamos similares.
          </Text>
        )}
        {duplicados?.candidatos.map((candidato) => (
          <Paper key={candidato.reclamo_id} withBorder p="xs" mb={6}>
            <Group justify="space-between" wrap="nowrap">
              <div>
                <Anchor size="sm" fw={500} onClick={() => onAbrirReclamo?.(candidato.reclamo_id)}>
                  {formatearIdReclamo(candidato.reclamo_id)} · {candidato.nombre_escuela}
                </Anchor>
                <Text size="xs" c="dimmed" lineClamp={2}>
                  {candidato.descripcion}
                </Text>
              </div>
              <Badge variant="light">{Math.round(candidato.similitud * 100)}%</Badge>
            </Group>
          </Paper>
        ))}
        <Button
          size="xs"
          variant="subtle"
          loading={buscandoDups}
          disabled={soloLectura}
          onClick={regenerarDuplicados}
          mt="xs"
        >
          Volver a buscar
        </Button>
      </Bloque>

      <Bloque titulo="Estimación preliminar">
        {cargandoEst && (
          <Text size="sm" c="dimmed">
            Cargando estimación…
          </Text>
        )}
        {!cargandoEst && !estimacion && (
          <Text size="sm" c="dimmed" mb="xs">
            Todavía no hay estimación para este reclamo.
          </Text>
        )}
        {estimacion && (
          <Stack gap={4} mb="xs">
            <Text size="sm">
              Materiales {formatoMoneda.format(Number(estimacion.materiales))} · Mano de obra{' '}
              {formatoMoneda.format(Number(estimacion.mano_obra))} · Otros{' '}
              {formatoMoneda.format(Number(estimacion.otros))}
            </Text>
            <Group gap="xs">
              <Text size="sm" fw={700}>
                Total {formatoMoneda.format(Number(estimacion.total))}
              </Text>
              {sinPrecedencias ? (
                <Badge size="xs" color="gray" variant="light">
                  Sin precedentes históricos
                </Badge>
              ) : (
                <Badge
                  size="xs"
                  variant="light"
                  color={Math.round(estimacion.confianza * 100) < 50 ? 'yellow' : undefined}
                >
                  {Math.round(estimacion.confianza * 100)}% confianza
                </Badge>
              )}
            </Group>
            {aviso && (
              <Text size="xs" c="dimmed">
                {aviso}
              </Text>
            )}
            {estimacion.justificacion && <Text size="sm">{estimacion.justificacion}</Text>}
          </Stack>
        )}
        <Button
          size="xs"
          variant="subtle"
          loading={generandoEst}
          disabled={soloLectura}
          onClick={generar}
        >
          Regenerar estimación
        </Button>
      </Bloque>

      <Bloque titulo="Análisis de fotos">
        {!hayFotos && (
          <Text size="sm" c="dimmed">
            Este reclamo no tiene fotos de tipo imagen para analizar.
          </Text>
        )}
        {vision && (
          <Stack gap={4} mb="xs">
            <Badge size="xs" variant="light">
              Severidad {vision.severidad}
            </Badge>
            {vision.hallazgos.length > 0 && (
              <List size="sm" spacing={2}>
                {vision.hallazgos.map((h) => (
                  <List.Item key={h}>{h}</List.Item>
                ))}
              </List>
            )}
            {vision.sugerencia_descripcion && (
              <Text size="sm">{vision.sugerencia_descripcion}</Text>
            )}
          </Stack>
        )}
        {hayFotos && (
          <Button
            size="xs"
            variant="subtle"
            loading={analizando}
            disabled={soloLectura}
            onClick={analizar}
          >
            Reanalizar fotos
          </Button>
        )}
      </Bloque>

      <Button
        size="xs"
        variant="light"
        loading={orquestando}
        disabled={soloLectura}
        onClick={orquestar}
      >
        Regenerar todo el análisis
      </Button>
    </Stack>
  );
}
