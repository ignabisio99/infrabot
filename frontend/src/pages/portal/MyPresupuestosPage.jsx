import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';

import { listarMisPresupuestos } from '../../api/contratistas';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';
import { estaVigente } from '../budgets/estados';

function BotonEditar({ presupuesto }) {
  const navigate = useNavigate();
  if (!presupuesto.editable) return null;
  const ajustar = presupuesto.estado === 'AJUSTES_SOLICITADOS';
  return (
    <Button
      size="xs"
      variant={ajustar ? 'filled' : 'light'}
      color={ajustar ? 'orange' : undefined}
      onClick={() => navigate(`/portal/reclamos/${presupuesto.reclamo.id}/presupuestar`)}
    >
      {ajustar ? 'Ajustar' : 'Editar'}
    </Button>
  );
}

function EstadoOferta({ presupuesto: p }) {
  return (
    <Group gap={4}>
      {p.reclamo.estado === 'CANCELADO' && estaVigente(p) ? (
        // Quedó en carrera cuando se canceló el reclamo: su estado ya no
        // describe nada que el contratista pueda hacer.
        <Badge color="gray" tt="none">
          Reclamo cancelado
        </Badge>
      ) : (
        <BudgetStatusBadge estado={p.estado} />
      )}
      {p.version > 1 && (
        <Badge color="gray" variant="outline" tt="none">
          Versión {p.version}
        </Badge>
      )}
    </Group>
  );
}

export function MyPresupuestosPage() {
  const esMobile = useEsMobile();
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [seleccionado, setSeleccionado] = useState(null);

  useEffect(() => {
    listarMisPresupuestos()
      .then(setPresupuestos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  return (
    <Container size="md" px={0}>
      <Title order={2} mb="lg">
        Mis presupuestos
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="No se pudieron cargar tus presupuestos">
          {error}
        </Alert>
      )}

      {!cargando && !error && presupuestos.length === 0 && (
        <Text c="dimmed">Todavía no cargaste ningún presupuesto.</Text>
      )}

      {!cargando && !error && presupuestos.length > 0 && esMobile && (
        <Stack gap="sm">
          {presupuestos.map((p) => (
            <TarjetaMovil
              key={p.id}
              onClick={() => setSeleccionado(p)}
              titulo={`${formatearIdReclamo(p.reclamo.id)} · ${p.reclamo.nombre_escuela}`}
              badges={<EstadoOferta presupuesto={p} />}
              campos={[
                { etiqueta: 'Monto', valor: formatoMoneda.format(Number(p.monto)) },
                { etiqueta: 'Fecha', valor: new Date(p.fecha).toLocaleDateString('es-AR') },
                { etiqueta: 'Ítems', valor: String(p.items.length) },
              ]}
              pie={p.editable && <BotonEditar presupuesto={p} />}
            />
          ))}
        </Stack>
      )}

      {!cargando && !error && presupuestos.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={600}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Reclamo</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Monto</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Ítems</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {presupuestos.map((p) => (
                <Table.Tr
                  key={p.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSeleccionado(p)}
                >
                  <Table.Td>{formatearIdReclamo(p.reclamo.id)}</Table.Td>
                  <Table.Td>{p.reclamo.nombre_escuela}</Table.Td>
                  <Table.Td>{new Date(p.fecha).toLocaleDateString('es-AR')}</Table.Td>
                  <Table.Td>{formatoMoneda.format(Number(p.monto))}</Table.Td>
                  <Table.Td>
                    <EstadoOferta presupuesto={p} />
                  </Table.Td>
                  <Table.Td>{p.items.length}</Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    <BotonEditar presupuesto={p} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <BudgetItemsModal
        presupuesto={seleccionado}
        onClose={() => setSeleccionado(null)}
        acciones={seleccionado && <BotonEditar presupuesto={seleccionado} />}
      />
    </Container>
  );
}
