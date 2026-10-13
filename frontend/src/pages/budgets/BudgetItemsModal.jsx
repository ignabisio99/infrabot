import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Divider,
  Group,
  Loader,
  Modal,
  ScrollArea,
  Table,
  Text,
} from '@mantine/core';

import { IconGavel } from '@tabler/icons-react';

import { auditarPresupuesto, obtenerAuditoria } from '../../api/ai';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda, formatoNumero } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';
import { esAdministrador } from '../../utils/auth';
import { DecideBudgetModal } from './DecideBudgetModal';

const colorPorRecomendacion = {
  APROBAR: 'green',
  REVISAR: 'yellow',
  RECHAZAR: 'red',
};

function GrupoItems({ titulo, items }) {
  if (items.length === 0) {
    return (
      <Text size="sm" c="dimmed" mb="sm">
        Sin {titulo.toLowerCase()}.
      </Text>
    );
  }

  return (
    <>
      <Text size="sm" fw={600} mb={4}>
        {titulo}
      </Text>
      <ScrollArea.Autosize mah={280} mb="md">
        <Table withColumnBorders striped miw={500}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w="45%">Descripción</Table.Th>
              <Table.Th>Cantidad</Table.Th>
              <Table.Th>Costo unitario</Table.Th>
              <Table.Th>Subtotal</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.id}>
                <Table.Td>{item.descripcion}</Table.Td>
                <Table.Td>
                  {formatoNumero.format(Number(item.cantidad))} {item.unidad ?? ''}
                </Table.Td>
                <Table.Td>{formatoMoneda.format(Number(item.costo_unitario))}</Table.Td>
                <Table.Td>{formatoMoneda.format(Number(item.subtotal))}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea.Autosize>
    </>
  );
}

export function BudgetItemsModal({ presupuesto, onClose, onDecidido }) {
  const [informe, setInforme] = useState(null);
  const [cargadoPara, setCargadoPara] = useState(null);
  const [recalculando, setRecalculando] = useState(false);
  const [decidirAbierto, setDecidirAbierto] = useState(false);
  const esAdmin = esAdministrador();
  const cargando = esAdmin && presupuesto !== null && cargadoPara !== presupuesto.id;
  const puedeDecidir = esAdmin && (presupuesto?.estados_posibles?.length ?? 0) > 0;

  useEffect(() => {
    // La auditoría es una evaluación interna del organismo: el contratista no la ve.
    if (!presupuesto || !esAdmin) return;
    let vigente = true;
    obtenerAuditoria(presupuesto.id)
      .then((data) => {
        if (vigente) setInforme(data);
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
  }, [presupuesto, esAdmin]);

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
        presupuesto
          ? `Ítems del presupuesto — ${formatearIdReclamo(presupuesto.reclamo.id)}${
              presupuesto.intento > 1 ? ` · intento ${presupuesto.intento}` : ''
            }`
          : ''
      }
      size="min(1100px, 92vw)"
    >
      {presupuesto && (
        <>
          {presupuesto.motivo_rechazo && (
            <Alert color="red" mb="md" title="Motivo del rechazo">
              {presupuesto.motivo_rechazo}
            </Alert>
          )}

          {presupuesto.detalle_tarea && (
            <>
              <Text size="sm" fw={600} mb={4}>
                Detalle de la tarea
              </Text>
              <Text size="sm" c="dimmed" mb="md" style={{ whiteSpace: 'pre-wrap' }}>
                {presupuesto.detalle_tarea}
              </Text>
            </>
          )}

          {presupuesto.observaciones && (
            <>
              <Text size="sm" fw={600} mb={4}>
                Observaciones
              </Text>
              <Text size="sm" c="dimmed" mb="md" style={{ whiteSpace: 'pre-wrap' }}>
                {presupuesto.observaciones}
              </Text>
            </>
          )}

          <GrupoItems
            titulo="Materiales"
            items={presupuesto.items.filter((i) => i.tipo !== 'MANO_OBRA')}
          />
          <GrupoItems
            titulo="Mano de obra"
            items={presupuesto.items.filter((i) => i.tipo === 'MANO_OBRA')}
          />

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
              {informe.sin_precedentes && (
                <Text size="sm" mb={4}>
                  Sin precedentes históricos: no se compara contra una estimación en $0.
                </Text>
              )}
              <Text size="sm">
                Presupuesto {formatoMoneda.format(Number(informe.total_presupuesto))}
                {informe.total_estimacion != null && !informe.sin_precedentes
                  ? ` · Estimación ${formatoMoneda.format(Number(informe.total_estimacion))}`
                  : ''}
                {desvioPct != null
                  ? ` · Desvío ${desvioPct.toFixed(1)}%${desvioPct < 0 ? ' por debajo' : ''}`
                  : ''}
              </Text>
              {informe.notas_tecnicas && (
                <Text size="sm" mt={4}>
                  {informe.notas_tecnicas}
                </Text>
              )}
            </Alert>
          )}

          {esAdmin && !cargando && !informe && (
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
              {esAdmin && (
                <Button variant="subtle" size="xs" loading={recalculando} onClick={recalcular}>
                  Recalcular auditoría
                </Button>
              )}
              {puedeDecidir && (
                <Button
                  size="xs"
                  color="teal"
                  leftSection={<IconGavel size={14} />}
                  onClick={() => setDecidirAbierto(true)}
                >
                  Aprobar / Rechazar
                </Button>
              )}
              <Text fw={700} size="lg">
                Total: {formatoMoneda.format(Number(presupuesto.monto))}
              </Text>
            </Group>
          </Group>

          <DecideBudgetModal
            presupuesto={decidirAbierto ? presupuesto : null}
            onClose={() => setDecidirAbierto(false)}
            onDecidido={() => {
              setDecidirAbierto(false);
              onDecidido?.();
              onClose();
            }}
          />
        </>
      )}
    </Modal>
  );
}
