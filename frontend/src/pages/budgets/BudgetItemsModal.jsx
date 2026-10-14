import { useEffect, useState } from 'react';
import {
  Accordion,
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

import { IconCheck, IconGavel } from '@tabler/icons-react';

import { auditarPresupuesto, obtenerAuditoria } from '../../api/ai';
import { obtenerVersionesPresupuesto } from '../../api/presupuestos';
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
            {items.map((item, index) => (
              <Table.Tr key={item.id ?? index}>
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

function VersionesAnteriores({ presupuestoId }) {
  const [versiones, setVersiones] = useState(null);

  useEffect(() => {
    let vigente = true;
    obtenerVersionesPresupuesto(presupuestoId)
      .then((data) => {
        if (vigente) setVersiones(data);
      })
      .catch((err) => notifyError(err.message));
    return () => {
      vigente = false;
    };
  }, [presupuestoId]);

  if (!versiones) return <Loader size="sm" mb="md" />;

  return (
    <>
      <Text size="sm" fw={600} mb={4}>
        Versiones anteriores
      </Text>
      <Accordion variant="contained" mb="md">
        {[...versiones].reverse().map((version) => (
          <Accordion.Item key={version.numero} value={String(version.numero)}>
            <Accordion.Control>
              <Group gap="xs">
                <Text size="sm" fw={500}>
                  Versión {version.numero}
                </Text>
                <Text size="sm" c="dimmed">
                  {new Date(version.fecha_envio).toLocaleString('es-AR')} ·{' '}
                  {formatoMoneda.format(Number(version.monto))}
                </Text>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              {version.ajustes_solicitados && (
                <Alert color="orange" mb="sm" title="Ajustes que se pidieron sobre esta versión">
                  {version.ajustes_solicitados}
                </Alert>
              )}
              {version.detalle_tarea && (
                <Text size="sm" c="dimmed" mb="sm" style={{ whiteSpace: 'pre-wrap' }}>
                  {version.detalle_tarea}
                </Text>
              )}
              <GrupoItems
                titulo="Materiales"
                items={version.items.filter((i) => i.tipo !== 'MANO_OBRA')}
              />
              <GrupoItems
                titulo="Mano de obra"
                items={version.items.filter((i) => i.tipo === 'MANO_OBRA')}
              />
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
    </>
  );
}

export function BudgetItemsModal({ presupuesto, onClose, onDecidido }) {
  const [informe, setInforme] = useState(null);
  const [cargadoPara, setCargadoPara] = useState(null);
  const [recalculando, setRecalculando] = useState(false);
  const [decidirAbierto, setDecidirAbierto] = useState(false);
  const esAdmin = esAdministrador();
  const aprobado = presupuesto?.estado === 'APROBADO';
  // La auditoría solo se carga para admins y mientras el presupuesto no esté aprobado
  const mostrarAuditoria = esAdmin && !aprobado;
  const cargando = mostrarAuditoria && presupuesto !== null && cargadoPara !== presupuesto.id;
  const puedeDecidir = esAdmin && (presupuesto?.estados_posibles?.length ?? 0) > 0;

  useEffect(() => {
    // La auditoría es una evaluación interna del organismo: el contratista no la ve.
    // Tampoco tiene sentido mostrarla una vez que el presupuesto fue aprobado.
    if (!presupuesto || !mostrarAuditoria) return;
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
  }, [presupuesto, mostrarAuditoria]);

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
        presupuesto ? (
          <Group gap="xs" wrap="nowrap">
            <Text fw={600}>
              {`Ítems del presupuesto — ${formatearIdReclamo(presupuesto.reclamo.id)}${
                presupuesto.version > 1 ? ` · versión ${presupuesto.version}` : ''
              }`}
            </Text>
            {aprobado && (
              <Badge color="green" variant="filled" leftSection={<IconCheck size={12} />}>
                Aprobado
              </Badge>
            )}
          </Group>
        ) : (
          ''
        )
      }
      size="min(1100px, 92vw)"
    >
      {presupuesto && (
        <>
          {aprobado && (
            <Alert
              color="green"
              mb="md"
              title="Presupuesto aprobado"
              icon={<IconCheck size={16} />}
            >
              Este presupuesto ya fue aprobado y adjudicado.
            </Alert>
          )}

          {presupuesto.motivo_estado && (
            <Alert
              color={presupuesto.estado === 'RECHAZADO' ? 'red' : 'orange'}
              mb="md"
              title={
                presupuesto.estado === 'RECHAZADO' ? 'Motivo del rechazo' : 'Ajustes solicitados'
              }
            >
              {presupuesto.motivo_estado}
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

          {presupuesto.version > 1 && <VersionesAnteriores presupuestoId={presupuesto.id} />}

          <Divider mb="sm" />

          {cargando && <Loader size="sm" mb="sm" />}

          {mostrarAuditoria && !cargando && informe && (
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

          {mostrarAuditoria && !cargando && !informe && (
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
              {mostrarAuditoria && (
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
                  Decidir
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
