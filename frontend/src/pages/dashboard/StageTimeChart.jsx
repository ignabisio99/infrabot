import { Badge, Card, Group, Text, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { useNavigate } from 'react-router';

import classes from './Dashboard.module.css';
import { etapaPorClave } from './etapas';

function textoDias(dias) {
  return `${dias.toLocaleString('es-AR')} ${dias === 1 ? 'día' : 'días'}`;
}

/**
 * Días promedio que un reclamo pasa en cada etapa abierta, para ver dónde se traba el
 * flujo. La etapa más lenta va marcada: es la pregunta que el gráfico viene a responder.
 *
 * `etiquetaPeriodo` es el texto del período en que terminaron las estadías medidas.
 */
export function StageTimeChart({ datos, etiquetaPeriodo, linkReclamos }) {
  const navigate = useNavigate();
  const conDatos = datos.filter((fila) => fila.dias_promedio !== null);
  const maximo = Math.max(...conDatos.map((fila) => fila.dias_promedio), 0);
  const masLenta = conDatos.length > 1 ? conDatos.find((f) => f.dias_promedio === maximo) : null;

  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Title order={4}>Tiempo promedio por etapa</Title>
      <Text size="xs" c="dimmed" mb="md">
        Días que pasa un reclamo en cada etapa, de los que la terminaron en los últimos{' '}
        {etiquetaPeriodo}.
      </Text>

      {conDatos.length === 0 ? (
        <Text c="dimmed" size="sm">
          Ningún reclamo terminó una etapa en el período.
        </Text>
      ) : (
        <div className={classes.barras}>
          {datos.map((fila) => {
            const etapa = etapaPorClave[fila.etapa];
            const sinDatos = fila.dias_promedio === null;
            const ancho = sinDatos || maximo === 0 ? 0 : (fila.dias_promedio / maximo) * 100;

            return (
              <Tooltip
                key={fila.etapa}
                label={
                  sinDatos
                    ? 'Ningún reclamo terminó esta etapa en el período'
                    : `Promedio de ${fila.reclamos} ${fila.reclamos === 1 ? 'reclamo' : 'reclamos'}`
                }
                position="top"
                withArrow
              >
                <UnstyledButton
                  className={classes.barraFila}
                  onClick={() => navigate(linkReclamos(etapa.estados))}
                >
                  <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
                    {etapa.nombre}
                  </Text>
                  <div className={classes.barraPista}>
                    <div
                      style={{
                        width: `${Math.max(ancho, sinDatos ? 0 : 1)}%`,
                        height: '100%',
                        // Recto contra la línea de base y redondeado sólo en la punta.
                        borderRadius: '0 4px 4px 0',
                        backgroundColor: etapa.color,
                      }}
                    />
                  </div>
                  <Group gap={6} justify="flex-end" wrap="nowrap" className={classes.barraValor}>
                    {masLenta?.etapa === fila.etapa && (
                      <Badge size="xs" variant="light" color="gray">
                        Más lenta
                      </Badge>
                    )}
                    <Text size="sm" fw={600} ta="right" c={sinDatos ? 'dimmed' : undefined}>
                      {sinDatos ? '—' : textoDias(fila.dias_promedio)}
                    </Text>
                  </Group>
                </UnstyledButton>
              </Tooltip>
            );
          })}
        </div>
      )}
    </Card>
  );
}
