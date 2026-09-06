import { Card, Text, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { useNavigate } from 'react-router-dom';

import { colorPorEstado, etiquetaPorEstado } from '../claims/estados';
import classes from './Dashboard.module.css';

// Ancho mínimo de barra para que un reclamo suelto se vea aunque otra etapa tenga
// muchos: sin esto una barra de 1 sobre 40 queda en 2px y parece cero.
const ANCHO_MINIMO = 2;

/**
 * Reclamos por estado, en el orden del flujo (mismo orden del enum del backend).
 *
 * Barras propias en vez de un gráfico de la librería porque los colores tienen que ser
 * exactamente los de `colorPorEstado`, que son los que ya usan los badges en toda la
 * app: el estado se reconoce por el mismo color en el listado y acá.
 */
export function ClaimsByStateChart({ datos }) {
  const navigate = useNavigate();
  const maximo = Math.max(...datos.map((fila) => fila.cantidad), 1);
  const total = datos.reduce((suma, fila) => suma + fila.cantidad, 0);

  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Title order={4}>Reclamos por estado</Title>
      <Text size="xs" c="dimmed" mb="md">
        Todas las etapas del flujo. Hacé clic para ver el listado filtrado.
      </Text>

      {total === 0 ? (
        <Text c="dimmed" size="sm">
          Todavía no hay reclamos registrados.
        </Text>
      ) : (
        <div className={classes.estados}>
          {datos.map(({ estado, cantidad }) => {
            const porcentaje =
              cantidad === 0 ? 0 : Math.max((cantidad / maximo) * 100, ANCHO_MINIMO);

            return (
              <Tooltip
                key={estado}
                label={`${cantidad} ${cantidad === 1 ? 'reclamo' : 'reclamos'}`}
                position="top"
                withArrow
              >
                <UnstyledButton
                  className={classes.estadoFila}
                  onClick={() => navigate(`/reclamos?estado=${estado}`)}
                >
                  <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
                    {etiquetaPorEstado[estado] ?? estado}
                  </Text>
                  <div style={{ height: 10 }}>
                    <div
                      style={{
                        width: `${porcentaje}%`,
                        height: '100%',
                        // Recto contra la línea de base y redondeado sólo en la punta,
                        // que es donde se lee el valor.
                        borderRadius: '0 4px 4px 0',
                        backgroundColor: `var(--mantine-color-${colorPorEstado[estado]}-6)`,
                      }}
                    />
                  </div>
                  <Text size="sm" fw={600} ta="right">
                    {cantidad}
                  </Text>
                </UnstyledButton>
              </Tooltip>
            );
          })}
        </div>
      )}
    </Card>
  );
}
