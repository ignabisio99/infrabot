import { Divider, Group, Modal, ScrollArea, Table, Text } from '@mantine/core';

import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda, formatoNumero } from '../../utils/formatters';

export function BudgetItemsModal({ presupuesto, onClose }) {
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

          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {presupuesto.items.length} {presupuesto.items.length === 1 ? 'ítem' : 'ítems'} ·
              cantidad total:{' '}
              {formatoNumero.format(
                presupuesto.items.reduce((acumulado, item) => acumulado + Number(item.cantidad), 0),
              )}
            </Text>
            <Text fw={700} size="lg">
              Total: {formatoMoneda.format(Number(presupuesto.monto))}
            </Text>
          </Group>
        </>
      )}
    </Modal>
  );
}
