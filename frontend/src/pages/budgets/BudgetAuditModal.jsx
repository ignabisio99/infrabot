import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Group, Loader, Modal, Stack, Text } from '@mantine/core';

import { auditarPresupuesto, obtenerAuditoria } from '../../api/ai';
import { formatoMoneda } from '../../utils/formatters';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError } from '../../utils/notifications';
import { estadosFinales } from '../claims/estados';

const colorPorRecomendacion = {
  APROBAR: 'green',
  REVISAR: 'yellow',
  RECHAZAR: 'red',
};

export function BudgetAuditModal({ presupuesto, onClose }) {
  const [informe, setInforme] = useState(null);
  const [cargadoPara, setCargadoPara] = useState(null);
  const [recalculando, setRecalculando] = useState(false);
  const reclamoCerrado = estadosFinales.includes(presupuesto?.reclamo?.estado);
  const cargando = presupuesto !== null && cargadoPara !== presupuesto.id;

  useEffect(() => {
    if (!presupuesto) return;
    let vigente = true;
    obtenerAuditoria(presupuesto.id)
      .then((data) => {
        if (!vigente) return;
        // Con el reclamo cerrado el backend ya no audita: se muestra lo guardado, si hay.
        if (data || reclamoCerrado) {
          setInforme(data);
          return;
        }
        return auditarPresupuesto(presupuesto.id).then((nuevo) => {
          if (vigente) setInforme(nuevo);
        });
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      })
      .finally(() => {
        if (vigente) setCargadoPara(presupuesto.id);
      });
    return () => {
      vigente = false;
      setInforme(null);
      setCargadoPara(null);
    };
  }, [presupuesto, reclamoCerrado]);

  const recalcular = async () => {
    if (!presupuesto) return;
    setRecalculando(true);
    try {
      const data = await auditarPresupuesto(presupuesto.id);
      setInforme(data);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setRecalculando(false);
    }
  };

  const desvioPct =
    informe?.desvio_porcentual != null ? Number(informe.desvio_porcentual) * 100 : null;

  return (
    <Modal
      opened={presupuesto !== null}
      onClose={onClose}
      title={
        presupuesto ? `Auditoría — ${formatearIdReclamo(presupuesto.reclamo.id)}` : 'Auditoría'
      }
    >
      {cargando && <Loader />}

      {!cargando && !informe && reclamoCerrado && (
        <Alert color="yellow" title="Sin auditoría guardada">
          El reclamo está cerrado, así que ya no se puede auditar.
        </Alert>
      )}

      {!cargando && informe && (
        <Stack gap="sm">
          {informe.sin_estimacion && (
            <Alert color="yellow" title="Sin estimación preliminar">
              La estimación se genera al dar de alta el reclamo. Si falta, regenerala desde el
              detalle.
            </Alert>
          )}
          {informe.sin_precedentes && (
            <Alert color="yellow" title="Sin precedentes históricos">
              No hay ancla de costos similares. No se usa una estimación en $0 para rechazar el
              presupuesto: hay que revisarlo con criterio técnico.
            </Alert>
          )}

          <Group gap="xs">
            <Text size="sm" fw={600}>
              Recomendación
            </Text>
            <Badge color={colorPorRecomendacion[informe.recomendacion] || 'gray'} tt="none">
              {informe.recomendacion}
            </Badge>
          </Group>

          <Text size="sm">
            Presupuesto: {formatoMoneda.format(Number(informe.total_presupuesto))}
          </Text>
          <Text size="sm">
            Estimación:{' '}
            {informe.total_estimacion != null
              ? formatoMoneda.format(Number(informe.total_estimacion))
              : '—'}
          </Text>
          <Text size="sm">
            Desvío:{' '}
            {informe.desvio_absoluto != null
              ? formatoMoneda.format(Number(informe.desvio_absoluto))
              : '—'}
            {desvioPct != null
              ? ` (${desvioPct.toFixed(1)}%${desvioPct < 0 ? ' por debajo' : ''})`
              : ''}
          </Text>

          <Text size="sm">{informe.notas_tecnicas}</Text>

          <Group>
            <Button
              variant="subtle"
              loading={recalculando}
              disabled={reclamoCerrado}
              onClick={recalcular}
            >
              Recalcular
            </Button>
            <Button variant="default" onClick={onClose}>
              Cerrar
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
