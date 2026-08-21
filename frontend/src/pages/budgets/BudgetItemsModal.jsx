import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Divider, Group, Loader, Modal, ScrollArea, Table, Text } from '@mantine/core';

import { auditarPresupuesto, obtenerAuditoria } from '../../api/ai';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda, formatoNumero } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';

const colorPorRecomendacion = {
  APROBAR: 'green',
  REVISAR: 'yellow',
  RECHAZAR: 'red',
};

export function BudgetItemsModal({ presupuesto, onClose }) {
  const [informe, setInforme] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [recalculando, setRecalculando] = useState(false);

  useEffect(() => {
    if (!presupuesto) {
      setInforme(null);
      return;
    }
    let vigente = true;
    setCargando(true);
    obtenerAuditoria(presupuesto.id)
      .then((data) => {
        if (vigente) setInforme(data);
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [presupuesto]);

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
        presupuesto ? `Ítems del presupuesto — ${formatearIdReclamo(presupuesto.reclamo.id)}` : ''
      }
      size="min(1100px, 92vw)"
    >
      {presupuesto && (
        <>
          <ScrollArea.Autosize mah={400} mb="md">
            <Table withColumnBorders striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w="45%">Descripción</Table.Th>
                  <Table.Th>Cantidad</Table.Th>
                  <Table.Th>Costo unitario</Table.Th>
                  <Table.Th>Subtotal</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {presupuesto.items.map((item) => (
                  <Table.Tr key={item.id}>
                    <Table.Td>{item.descripcion}</Table.Td>
                    <Table.Td>{formatoNumero.format(Number(item.cantidad))}</Table.Td>
                    <Table.Td>{formatoMoneda.format(Number(item.costo_unitario))}</Table.Td>
                    <Table.Td>{formatoMoneda.format(Number(item.subtotal))}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea.Autosize>

          <Divider mb="sm" />

          {cargando && <Loader size="sm" mb="sm" />}

          {!cargando && informe && (
            <Alert
              mb="sm"
              color={colorPorRecomendacion[informe.recomendacion] || 'gray'}
              title={
                <Group gap="xs">
                  <Text span>Auditoría automática</Text>
                  <Badge color={colorPorRecomendacion[informe.recomendacion] || 'gray'} tt="none">
                    {informe.recomendacion}
                  </Badge>
                </Group>
              }
            >
              <Text size="sm">
                Presupuesto {formatoMoneda.format(Number(informe.total_presupuesto))}
                {informe.total_estimacion != null
                  ? ` · Estimación ${formatoMoneda.format(Number(informe.total_estimacion))}`
                  : ''}
                {desvioPct != null ? ` · Desvío ${desvioPct.toFixed(1)}%` : ''}
              </Text>
              {informe.notas_tecnicas && (
                <Text size="sm" mt={4}>
                  {informe.notas_tecnicas}
                </Text>
              )}
            </Alert>
          )}

          {!cargando && !informe && (
            <Alert color="yellow" mb="sm" title="Sin auditoría guardada">
              Al guardar el presupuesto se audita solo. Podés recalcular ahora.
            </Alert>
          )}

          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {presupuesto.items.length} {presupuesto.items.length === 1 ? 'ítem' : 'ítems'} ·
              cantidad total:{' '}
              {formatoNumero.format(
                presupuesto.items.reduce((acumulado, item) => acumulado + Number(item.cantidad), 0),
              )}
            </Text>
            <Group>
              <Button variant="subtle" size="xs" loading={recalculando} onClick={recalcular}>
                Recalcular auditoría
              </Button>
              <Text fw={700} size="lg">
                Total: {formatoMoneda.format(Number(presupuesto.monto))}
              </Text>
            </Group>
          </Group>
        </>
      )}
    </Modal>
  );
}
